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
