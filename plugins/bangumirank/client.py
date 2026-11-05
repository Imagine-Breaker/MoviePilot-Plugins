"""Bangumi Official API v0 Client.

Supports authentication with Personal Access Token, HTTP/SOCKS proxy,
strict rate-limiting, and endpoints for user info, collections, calendar,
subjects, episodes, and collection updates.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
import requests
from app.log import logger


class BangumiClient:
    BASE_URL = "https://api.bgm.tv"
    USER_AGENT = "MoviePilot-BangumiRank/0.1 (https://github.com/honue/MoviePilot-Plugins)"

    def __init__(self, token: str = "", proxy: str = "", interval: float = 1.0):
        self.interval = max(0.2, float(interval))
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        token = str(token or "").strip()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        proxy = str(proxy or "").strip()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self._last_request = 0.0

    def _throttle(self) -> None:
        gap = time.time() - self._last_request
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self._last_request = time.time()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        timeout: int = 15,
    ) -> Any:
        url = f"{self.BASE_URL}{path}" if path.startswith("/") else f"{self.BASE_URL}/{path}"
        for attempt in range(1, 4):
            self._throttle()
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=timeout,
                )
            except requests.RequestException as err:
                logger.warning(f"Bangumi API 请求异常 (第{attempt}次重试): {err}")
                time.sleep(1.0 * attempt)
                continue

            if resp.status_code == 429:
                logger.warning(f"Bangumi API 429 频率限制，等待重试...")
                time.sleep(2.0 * attempt)
                continue
            if resp.status_code in (200, 201, 202, 204):
                if resp.status_code == 204 or not resp.text.strip():
                    return True
                try:
                    return resp.json()
                except ValueError:
                    return True
            if resp.status_code == 404:
                return None
            logger.warning(f"Bangumi API 返回错误 [{resp.status_code}]: {resp.text[:120]}")
            return None
        return None

    def get_me(self) -> Optional[Dict[str, Any]]:
        """获取当前登录用户信息 (验证 Token 连通性)"""
        data = self._request("GET", "/v0/me")
        if isinstance(data, dict) and data.get("id"):
            return data
        return None

    def get_user_collections(
        self,
        username: str,
        subject_type: int = 2,
        collection_type: int = 1,
        ctype: Optional[int] = None,
        limit: int = 30,
        offset: int = 0,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        获取用户指定分类的条目收藏
        subject_type: 2=动画
        collection_type: 1=想看, 2=看过, 3=在看, 4=搁置, 5=抛弃
        """
        c_type = ctype if ctype is not None else collection_type
        params = {
            "subject_type": subject_type,
            "type": c_type,
            "limit": min(limit, 50),
            "offset": offset,
        }
        res = self._request("GET", f"/v0/users/{username}/collections", params=params)
        if isinstance(res, dict) and "data" in res:
            return res.get("data") or []
        return []

    def get_calendar(self) -> List[Dict[str, Any]]:
        """获取当季每日放送列表 (周一至周日更新的最新番剧)"""
        res = self._request("GET", "/calendar")
        items = []
        if isinstance(res, list):
            for day in res:
                weekday_name = (day.get("weekday") or {}).get("cn", "")
                for item in day.get("items") or []:
                    item["weekday"] = weekday_name
                    items.append(item)
        return items

    def search_subjects(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索动画条目"""
        keyword = str(keyword or "").strip()
        if not keyword:
            return []
        payload = {
            "keyword": keyword,
            "sort": "match",
            "filter": {"type": [2]},
        }
        res = self._request("POST", "/v0/search/subjects", json_data=payload)
        if isinstance(res, dict) and "data" in res:
            return res.get("data") or []
        return []

    def get_subject(self, subject_id: int) -> Optional[Dict[str, Any]]:
        """获取条目详情"""
        res = self._request("GET", f"/v0/subjects/{subject_id}")
        return res if isinstance(res, dict) and res.get("id") else None

    def get_episodes(self, subject_id: int, ep_type: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """获取条目剧集列表 (ep_type: 0=正片)"""
        params = {"subject_id": subject_id, "type": ep_type, "limit": limit}
        res = self._request("GET", "/v0/episodes", params=params)
        if isinstance(res, dict) and "data" in res:
            return res.get("data") or []
        return []

    def update_collection_status(self, subject_id: int, status: int = 3, comment: str = "") -> bool:
        """
        更新当前用户条目收藏状态
        status: 1=想看, 2=看过, 3=在看, 4=搁置, 5=抛弃
        """
        payload = {"type": status, "comment": comment, "private": False}
        res = self._request("POST", f"/v0/users/-/collections/{subject_id}", json_data=payload)
        return bool(res)

    def update_episode_status(self, episode_id: int, status: int = 2) -> bool:
        """
        更新当前用户单集观看状态 (打格子)
        status: 0=未看, 1=想看, 2=看过, 3=抛弃
        """
        payload = {"type": status}
        res = self._request("PUT", f"/v0/users/-/collections/-/episodes/{episode_id}", json_data=payload)
        return bool(res)
