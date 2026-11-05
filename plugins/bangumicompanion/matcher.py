"""Bangumi and MoviePilot Media Recognition & Matcher."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from app.core.context import MediaInfo
from app.core.metainfo import MetaInfo
from app.log import logger
from app.schemas.types import MediaType


class BangumiMatcher:
    @staticmethod
    def match_subject_to_mediainfo(chain, subject: Dict[str, Any]) -> Tuple[Optional[MediaInfo], Optional[MetaInfo]]:
        """
        基于 Bangumi 条目元数据智能匹配 MoviePilot 媒体识别。
        强制锁定动画 TV/电影类型并核验动画分类，杜绝同名真人版电影误识别。
        """
        sid = subject.get("id")
        name_cn = str(subject.get("name_cn") or "").strip()
        name = str(subject.get("name") or "").strip()
        date_str = str(subject.get("date") or "").strip()
        year = date_str[:4] if len(date_str) >= 4 and date_str[:4].isdigit() else ""
        platform = str(subject.get("platform") or "").upper()
        eps = int(subject.get("eps") or 0)

        # 1. 严格推导媒体类型：剧场版/单集为 MOVIE，多集/TV/Web/OVA 强制锁定为 TV
        if platform == "MOVIE" or (eps == 1 and platform not in ["TV", "WEB", "OVA"]):
            expected_mtype = MediaType.MOVIE
        else:
            expected_mtype = MediaType.TV

        # 2. 优先利用 MoviePilot 原生内置的 Bangumi ↔ TMDb 官方映射库
        if sid:
            try:
                mediainfo = chain.recognize_media(bangumiid=sid, mtype=expected_mtype)
                if mediainfo and mediainfo.tmdb_id:
                    meta = MetaInfo(name_cn or name or mediainfo.title)
                    logger.info(f"Bangumi ID [{sid}] 直连映射成功: {mediainfo.title} ({mediainfo.year}) [TMDb: {mediainfo.tmdb_id}]")
                    return mediainfo, meta
            except Exception as err:
                logger.debug(f"Bangumi ID [{sid}] 直连识别跳过: {err}")

        # 3. 构造搜索候选项（优先使用中文名 + 年份，次选原名）
        candidates = []
        if name_cn and year:
            candidates.append(f"{name_cn} {year}")
        if name and year:
            candidates.append(f"{name} {year}")
        if name_cn:
            candidates.append(name_cn)
        if name:
            candidates.append(name)

        for query in candidates:
            try:
                meta = MetaInfo(query)
                # 显式传入 expected_mtype 封死反向跨类型搜索
                mediainfo = chain.recognize_media(meta=meta, mtype=expected_mtype)
                if not mediainfo or not mediainfo.tmdb_id:
                    continue

                # 4. 防真人版与跨类型防误识校验
                if expected_mtype == MediaType.TV and mediainfo.type == MediaType.MOVIE:
                    logger.warning(f"丢弃错误匹配：TV 动漫 [{query}] 被识别为电影 [{mediainfo.title}]")
                    continue

                # 5. 核验动画分类属性（TMDb 动画分类 ID 为 16）
                genre_ids = getattr(mediainfo, "genre_ids", []) or []
                genres = getattr(mediainfo, "genres", []) or []
                category = str(getattr(mediainfo, "category", "") or "")
                is_anime = (
                    16 in genre_ids
                    or any("动画" in str(g) or "Animation" in str(g) for g in genres)
                    or "动漫" in category
                )
                if not is_anime and (name_cn or name):
                    logger.warning(f"丢弃错误匹配：[{query}] 命中非动画真人影视 [{mediainfo.title}]")
                    continue

                logger.info(f"媒体识别成功: [{query}] -> {mediainfo.title} ({mediainfo.year}) [TMDb: {mediainfo.tmdb_id}]")
                return mediainfo, meta
            except Exception as err:
                logger.debug(f"媒体识别异常 [{query}]: {err}")
                continue

        return None, None

    @staticmethod
    def infer_season(chain, subject: Dict[str, Any], mediainfo: Optional[MediaInfo], meta: Optional[MetaInfo] = None) -> int:
        """
        基于 Bangumi 条目元数据与 TMDb 各季首播日期精准推导季度 (Season Number)。
        彻底解决“完结篇/最终季/分期”被误判为第 1 季的结构性冲突。
        """
        if not mediainfo or mediainfo.type != MediaType.TV:
            return 1

        bgm_date = str(subject.get("date") or "").strip()
        bgm_name_cn = str(subject.get("name_cn") or "")
        bgm_name = str(subject.get("name") or "")
        combined_title = f"{bgm_name_cn} {bgm_name}".strip()

        # 1. 尝试从 TMDb 获取该剧集的所有 Season 元数据
        tmdb_info = getattr(mediainfo, "tmdb_info", None)
        if not tmdb_info and hasattr(chain, "tmdb_info") and mediainfo.tmdb_id:
            try:
                tmdb_info = chain.tmdb_info(tmdbid=mediainfo.tmdb_id, mtype=MediaType.TV)
            except Exception:
                tmdb_info = None

        seasons = (tmdb_info.get("seasons") if isinstance(tmdb_info, dict) else None) or []
        valid_seasons = [s for s in seasons if isinstance(s, dict) and (s.get("season_number") or 0) > 0]

        # 2. 精准首播日期对齐：比对 Bangumi 首播日期与 TMDb 各季度的 air_date
        if bgm_date and len(bgm_date) >= 7 and valid_seasons:
            bgm_ym = bgm_date[:7]
            bgm_year = bgm_date[:4]
            # 2.1 年月完全一致 (如 2026-01 == 2026-01)
            for s in valid_seasons:
                s_air = str(s.get("air_date") or "").strip()
                if s_air.startswith(bgm_ym):
                    logger.info(f"季度精准年月对齐: [{combined_title}] ({bgm_date}) -> Season {s['season_number']}")
                    return int(s["season_number"])
            # 2.2 年份完全一致
            year_matched = [s for s in valid_seasons if str(s.get("air_date") or "").startswith(bgm_year)]
            if len(year_matched) == 1:
                logger.info(f"季度年份唯一对齐: [{combined_title}] ({bgm_date}) -> Season {year_matched[0]['season_number']}")
                return int(year_matched[0]["season_number"])

        # 3. 动漫语义规则推导
        # 3.1 最终季 / 最终章 / 完结篇 -> 自动对齐 TMDb 最新最大季
        if any(w in combined_title for w in ["最终季", "最终章", "完结篇", "完結編", "Final Season", "The Final"]):
            if valid_seasons:
                max_s = max(s.get("season_number", 1) for s in valid_seasons)
                logger.info(f"动漫语义推导 [最终季/完结篇]: [{combined_title}] -> 最大 Season {max_s}")
                return int(max_s)

        # 3.2 标题含有明确季数：第X季 / 第X期 / Season X / Part X
        import re
        patterns = [
            r"第\s*([0-9一二三四五六七八九十]+)\s*[季期]",
            r"(?:Season|S)\s*(\d+)",
            r"(\d+)(?:st|nd|rd|th)\s+Season",
            r"Part\s*(\d+)",
        ]
        cn_num = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        for pat in patterns:
            match = re.search(pat, combined_title, re.IGNORECASE)
            if match:
                val = match.group(1)
                num = cn_num.get(val) if val in cn_num else (int(val) if val.isdigit() else None)
                if num and num > 0:
                    logger.info(f"动漫语义推导 [季数提取]: [{combined_title}] -> Season {num}")
                    return int(num)

        # 4. MetaInfo 提取兜底
        if meta and meta.begin_season:
            return int(meta.begin_season)

        return 1

    @staticmethod
    def match_mediainfo_to_subject(client, mediainfo: Any, extra_info: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """
        根据 MoviePilot 的订阅元数据反向匹配 Bangumi Subject ID。
        支持从媒体标识 (bangumi:12345) 直接提取或根据标题检索。
        """
        if extra_info:
            bgm_id = extra_info.get("bangumiid") or extra_info.get("bangumi_id") or extra_info.get("mediaid") or ""
            if str(bgm_id).startswith(("bangumi:", "bgm:")):
                raw_id = str(bgm_id).split(":")[-1]
                if raw_id.isdigit():
                    return int(raw_id)
            elif isinstance(bgm_id, int) and bgm_id > 0:
                return bgm_id

        year = ""
        title = ""
        cn_title = ""
        if isinstance(mediainfo, dict):
            mediaid = mediainfo.get("mediaid") or mediainfo.get("bangumiid") or mediainfo.get("bangumi_id") or ""
            if str(mediaid).startswith(("bangumi:", "bgm:")):
                raw_id = str(mediaid).split(":")[-1]
                if raw_id.isdigit():
                    return int(raw_id)
            year = str(mediainfo.get("year") or "").strip()
            title = mediainfo.get("original_title") or mediainfo.get("title") or mediainfo.get("name") or ""
            cn_title = mediainfo.get("title") or ""
        elif mediainfo:
            year = str(getattr(mediainfo, "year", "") or "").strip()
            title = getattr(mediainfo, "original_title", "") or getattr(mediainfo, "title", "") or ""
            cn_title = getattr(mediainfo, "title", "") or ""

        queries = [str(q).strip() for q in [title, cn_title] if str(q).strip()]
        for q in queries:
            subjects = client.search_subjects(q)
            if subjects:
                if year:
                    for s in subjects:
                        s_date = str(s.get("date") or "")[:4]
                        if s_date == year:
                            return s.get("id")
                return subjects[0].get("id")

        return None
