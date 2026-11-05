import datetime
import threading
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.chain.download import DownloadChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, MediaType

try:
    from app.plugins.bangumicompanion.client import BangumiClient
    from app.plugins.bangumicompanion.matcher import BangumiMatcher
    from app.plugins.bangumicompanion.ui import BangumiUI
except ImportError:
    try:
        from .client import BangumiClient
        from .matcher import BangumiMatcher
        from .ui import BangumiUI
    except ImportError:
        from client import BangumiClient
        from matcher import BangumiMatcher
        from ui import BangumiUI


class BangumiCompanion(_PluginBase):
    plugin_name = "Bangumi追番伴侣"
    plugin_desc = "Bangumi 官方直连：个人想看/在看同步、订阅候选审核、MP订阅反向标在看"
    plugin_icon = "https://raw.githubusercontent.com/Imagine-Breaker/MoviePilot-Plugins/main/icons/miku.jpg"
    plugin_version = "1.0.0"
    plugin_author = "Imagine-Breaker"
    author_url = "https://github.com/Imagine-Breaker/MoviePilot-Plugins"
    plugin_config_prefix = "bangumicompanion_"
    plugin_order = 15
    auth_level = 1

    _event = threading.Event()
    downloadchain: DownloadChain = None
    subscribechain: SubscribeChain = None
    client: BangumiClient = None
    _scheduler: Optional[BackgroundScheduler] = None
    _user_info: Optional[dict] = None

    _enabled, _auto_subscribe, _onlyonce = False, False, False
    _token, _proxy, _cron = "", "", "0 8 * * *"
    _use_system_proxy, _clear = False, False
    _sync_wish, _sync_do = True, False
    _wish_top, _min_score = 20, 0.0
    _sync_mp_subscribe = True
    _include, _exclude = "", ""

    def init_plugin(self, config: dict = None):
        self.downloadchain = DownloadChain()
        self.subscribechain = SubscribeChain()

        if config:
            self._enabled = bool(config.get("enabled"))
            self._auto_subscribe = bool(config.get("auto_subscribe", False))
            self._token = str(config.get("token") or "").strip()
            self._proxy = str(config.get("proxy") or "").strip()
            self._use_system_proxy = bool(config.get("use_system_proxy"))
            self._cron = str(config.get("cron") or "0 8 * * *").strip()
            self._onlyonce = bool(config.get("onlyonce"))
            self._sync_wish = bool(config.get("sync_wish", True))
            self._sync_do = bool(config.get("sync_do", False))
            self._wish_top = int(config.get("wish_top") or 20)
            self._min_score = float(config.get("min_score") or 0.0)
            self._sync_mp_subscribe = bool(config.get("sync_mp_subscribe", True))
            self._include = str(config.get("include") or "").strip()
            self._exclude = str(config.get("exclude") or "").strip()
            self._clear = bool(config.get("clear"))

        proxy = self._proxy or (getattr(settings, "PROXY", "") if self._use_system_proxy else "")
        self.client = BangumiClient(token=self._token, proxy=proxy)
        if self._token:
            try:
                self._user_info = self.client.get_me()
                if self._user_info:
                    logger.info(f"Bangumi 认证成功: {self._user_info.get('nickname')} (UID: {self._user_info.get('id')})")
            except Exception as e:
                logger.warning(f"Bangumi 用户信息验证失败: {e}")

        self.stop_service()

        if self._clear:
            self.save_data("history", [])
            self.save_data("candidates", [])
            self._clear = False
            self.__update_config()

        if self._enabled or self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._enabled and self._cron:
                try:
                    self._scheduler.add_job(
                        func=self.__sync_all,
                        trigger=CronTrigger.from_crontab(self._cron),
                        name="Bangumi追番任务",
                    )
                    logger.info(f"Bangumi 追番服务已启动，周期：{self._cron}")
                except Exception as e:
                    logger.error(f"Bangumi 定时任务注册失败: {e}")
            if self._onlyonce:
                logger.info("Bangumi 追番服务立即执行一次")
                run_time = datetime.datetime.now(tz=pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=2)
                self._scheduler.add_job(func=self.__sync_all, trigger="date", run_date=run_time)
                self._onlyonce = False
                self.__update_config()

            if self._scheduler and self._scheduler.get_jobs():
                self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    def stop_service(self):
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止 Bangumi 任务失败: {e}")

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled, "auto_subscribe": self._auto_subscribe, "token": self._token,
            "proxy": self._proxy, "use_system_proxy": self._use_system_proxy, "cron": self._cron,
            "onlyonce": self._onlyonce, "sync_wish": self._sync_wish, "sync_do": self._sync_do,
            "wish_top": self._wish_top, "min_score": self._min_score, "sync_mp_subscribe": self._sync_mp_subscribe,
            "include": self._include, "exclude": self._exclude, "clear": self._clear,
        })

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {"path": "/subscribe_candidate", "endpoint": self.api_subscribe_candidate, "methods": ["GET", "POST"], "auth": "bear", "summary": "订阅单个候选"},
            {"path": "/ignore_candidate", "endpoint": self.api_ignore_candidate, "methods": ["GET", "POST"], "auth": "bear", "summary": "忽略单个候选"},
            {"path": "/subscribe_all_candidates", "endpoint": self.api_subscribe_all_candidates, "methods": ["GET", "POST"], "auth": "bear", "summary": "一键全订"},
            {"path": "/clear_candidates", "endpoint": self.api_clear_candidates, "methods": ["GET", "POST"], "auth": "bear", "summary": "清空候选"},
        ]

    def api_subscribe_candidate(self, candidate_id: Optional[str] = None) -> dict:
        if not candidate_id:
            return {"success": False, "message": "缺少 candidate_id 参数", "data": None}
        candidates = self.get_data("candidates") or []
        target = next((c for c in candidates if c.get("candidate_id") == candidate_id), None)
        if not target:
            return {"success": False, "message": "未找到候选条目", "data": None}
        ok, msg = self._execute_subscribe(target)
        if ok:
            self.save_data("candidates", [c for c in candidates if c.get("candidate_id") != candidate_id])
            return {"success": True, "message": f"已成功订阅: {target.get('bgm_title')}", "data": None}
        return {"success": False, "message": f"订阅失败: {msg}", "data": None}

    def api_ignore_candidate(self, candidate_id: Optional[str] = None) -> dict:
        if not candidate_id:
            return {"success": False, "message": "缺少 candidate_id 参数", "data": None}
        candidates = self.get_data("candidates") or []
        target = next((c for c in candidates if c.get("candidate_id") == candidate_id), None)
        if target:
            self.save_data("candidates", [c for c in candidates if c.get("candidate_id") != candidate_id])
            self._record_history(
                title=target.get("bgm_title"), category="已忽略候选", link=target.get("bgm_link"),
                poster=target.get("poster"), score=target.get("score"), unique_id=f"bgm:{target.get('subject_id')}",
            )
            return {"success": True, "message": f"已忽略: {target.get('bgm_title')}", "data": None}
        return {"success": False, "message": "未找到候选条目", "data": None}

    def api_subscribe_all_candidates(self) -> dict:
        candidates = self.get_data("candidates") or []
        success_count = 0
        remain_cands = []
        for cand in candidates:
            ok, _ = self._execute_subscribe(cand)
            if ok:
                success_count += 1
            else:
                remain_cands.append(cand)
        self.save_data("candidates", remain_cands)
        return {"success": True, "message": f"成功订阅 {success_count} 部番剧！", "data": None}

    def api_clear_candidates(self) -> dict:
        self.save_data("candidates", [])
        return {"success": True, "message": "候选列表已清空！", "data": None}

    def _execute_subscribe(self, item: dict) -> Tuple[bool, str]:
        try:
            raw_mtype = item.get("mtype")
            mtype = None
            if raw_mtype:
                try:
                    mtype = MediaType(raw_mtype)
                except Exception:
                    mtype = raw_mtype

            sub_id, msg = self.subscribechain.add(
                title=item.get("tmdb_title"),
                year=item.get("year"),
                mtype=mtype,
                tmdbid=item.get("tmdb_id"),
                season=item.get("season") or 1,
                exist_ok=True,
                username="Bangumi",
            )
            if not sub_id:
                return False, msg or "添加订阅失败"

            self._apply_subscribe_filter(sub_id)
            sid = item.get("subject_id")
            if self._token and sid:
                self.client.update_collection_status(sid, status=3)

            self._record_history(
                title=item.get("bgm_title") or item.get("tmdb_title"),
                category=f"已订阅 ({item.get('source', '手动')})",
                link=item.get("bgm_link") or f"https://bgm.tv/subject/{sid}",
                poster=item.get("poster"),
                unique_id=f"bgm:{sid}",
                score=item.get("score"),
            )
            return True, "成功"
        except Exception as err:
            logger.error(f"执行订阅异常: {err}")
            return False, str(err)

    @eventmanager.register(EventType.SubscribeAdded)
    def on_subscribe_added(self, event: Event):
        """MP 订阅反向同步：只要在 MP 订阅番剧，自动在 Bangumi 标记为在看"""
        if not self._enabled or not self._sync_mp_subscribe or not self.client or not self._token:
            return
        try:
            event_data = event.event_data or {}
            mediainfo = event_data.get("mediainfo") or {}
            sub_id = BangumiMatcher.match_mediainfo_to_subject(self.client, mediainfo, event_data.get("extra_info"))
            if sub_id:
                ok = self.client.update_collection_status(sub_id, status=3)
                title = mediainfo.get("title") or mediainfo.get("name") or "番剧"
                if ok:
                    logger.info(f"MP 订阅反向同步 Bangumi 成功: {title} (ID: {sub_id}) -> 已标为在看")
                    self._record_history(
                        title=f"{title}",
                        category="订阅同步 (在看)",
                        link=f"https://bgm.tv/subject/{sub_id}",
                        poster=mediainfo.get("poster_path") or "",
                        unique_id=f"mp_sub:{sub_id}",
                    )
        except Exception as e:
            logger.error(f"MP 订阅反向同步 Bangumi 失败: {e}")

    def __sync_all(self):
        logger.info(f"开始拉取 Bangumi 收藏 (模式: {'自动订阅' if self._auto_subscribe else '待确认候选'})...")
        subjects: List[Tuple[dict, str]] = []

        if self._token and self._user_info:
            username = self._user_info.get("username")
            if self._sync_wish:
                for item in self.client.get_user_collections(username, collection_type=1, limit=self._wish_top):
                    if item.get("subject"):
                        subjects.append((item["subject"], "想看"))
            if self._sync_do:
                for item in self.client.get_user_collections(username, collection_type=3, limit=self._wish_top):
                    if item.get("subject"):
                        subjects.append((item["subject"], "在看"))

        history = self.get_data("history") or []
        candidates = self.get_data("candidates") or []
        handled_uids = {h.get("unique") for h in history}
        cand_sub_ids = {c.get("subject_id") for c in candidates}

        for sub, source in subjects:
            if self._event.is_set():
                break
            sid = sub.get("id")
            if not sid or f"bgm:{sid}" in handled_uids or sid in cand_sub_ids:
                continue

            score = (sub.get("rating") or {}).get("score") if isinstance(sub.get("rating"), dict) else sub.get("score")
            if self._min_score > 0 and score and float(score) < self._min_score:
                continue

            try:
                mediainfo, meta = BangumiMatcher.match_subject_to_mediainfo(self.chain, sub)
                if not mediainfo or not mediainfo.tmdb_id:
                    continue

                if self.subscribechain.exists(mediainfo=mediainfo, meta=meta):
                    continue

                bgm_title = sub.get("name_cn") or sub.get("name") or mediainfo.title
                poster = mediainfo.get_poster_image() or (sub.get("images") or {}).get("common") or ""
                cand_data = {
                    "candidate_id": f"cand_{sid}",
                    "subject_id": sid,
                    "bgm_title": bgm_title,
                    "bgm_link": f"https://bgm.tv/subject/{sid}",
                    "source": source,
                    "poster": poster,
                    "score": score or "无",
                    "tmdb_id": mediainfo.tmdb_id,
                    "tmdb_title": mediainfo.title,
                    "year": mediainfo.year,
                    "season": meta.begin_season or 1,
                    "mtype": mediainfo.type.value if hasattr(mediainfo.type, "value") else str(mediainfo.type or ""),
                    "add_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                if self._auto_subscribe:
                    self._execute_subscribe(cand_data)
                    handled_uids.add(f"bgm:{sid}")
                else:
                    candidates.append(cand_data)
                    cand_sub_ids.add(sid)
                    logger.info(f"已加入候选队列: {bgm_title} -> TMDb: {mediainfo.title} ({mediainfo.year})")
            except Exception as err:
                logger.error(f"处理条目 [{sub.get('name')}] 失败: {err}")

        if not self._auto_subscribe:
            self.save_data("candidates", candidates)
        logger.info("Bangumi 收藏同步完成")

    def _apply_subscribe_filter(self, sub_id: int):
        try:
            from app.db import get_db
            from app.db.models.subscribe import Subscribe
            db = get_db()
            sub_record = Subscribe.get(db, sub_id)
            if sub_record:
                if self._include:
                    sub_record.include = self._include
                if self._exclude:
                    sub_record.exclude = self._exclude
                sub_record.update(db=db, payload=sub_record.to_dict())
        except Exception as e:
            logger.debug(f"设置过滤规则跳过: {e}")

    def _record_history(self, title: str, category: str, link: str = "", poster: str = "", unique_id: str = "", score: Any = None):
        history = self.get_data("history") or []
        history.insert(0, {
            "title": title,
            "type": category,
            "bangumi_link": link,
            "poster": poster or "https://raw.githubusercontent.com/honue/MoviePilot-Plugins/main/icons/miku.jpg",
            "score": score or "无",
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "unique": unique_id or f"action_{datetime.datetime.now().timestamp()}",
        })
        self.save_data("history", history[:100])

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return BangumiUI.render_form()

    def get_page(self) -> List[dict]:
        return BangumiUI.render_page(
            user_info=self._user_info,
            candidates=self.get_data("candidates") or [],
            history=self.get_data("history") or [],
            auto_subscribe=self._auto_subscribe,
        )
