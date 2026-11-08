"""MoviePilot 订阅存在性直查。

绕开 MP 原生 exists() 对 season / episode_group / media_source 的组合要求，
直接按 TMDb / Bangumi ID 查询订阅表与订阅历史表。

注意：MP 在订阅完成时会删除 subscribe 行并写入 subscribehistory，
因此必须同时查两张表，否则已完结的番每次运行都会被重新 add() 并重复通知。
"""

from __future__ import annotations

import datetime
from typing import Any, List, Optional

from app.log import logger
from app.schemas.types import MediaType


def _subscribed_seasons(tmdb_id: Any, bangumi_id: Any) -> List[int]:
    """查询同媒体的已订阅季号（订阅表 + 订阅历史表）。"""
    from sqlalchemy import or_, select
    from app.db import SessionFactory
    from app.db.models.subscribe import Subscribe
    from app.db.models.subscribehistory import SubscribeHistory

    seasons: List[int] = []
    db = SessionFactory()
    try:
        for table in (Subscribe, SubscribeHistory):
            conditions = []
            if tmdb_id:
                conditions.append(table.tmdbid == tmdb_id)
            if bangumi_id:
                conditions.append(table.bangumiid == bangumi_id)
            if not conditions:
                continue
            rows = db.execute(select(table).where(or_(*conditions))).scalars().all()
            seasons.extend(int(row.season or 1) for row in rows)
    finally:
        db.close()
    return seasons


def find_subscription_state(
        mediainfo: Any,
        season: Optional[int] = None,
        is_tv: bool = False,
) -> Optional[bool]:
    """
    查询同媒体订阅状态。

    :return: None=从未订阅过；True=该季已订阅/已完结；False=订阅过但不是这一季
    """
    try:
        seasons = _subscribed_seasons(
            getattr(mediainfo, "tmdb_id", None),
            getattr(mediainfo, "bangumi_id", None),
        )
        if not seasons:
            return None
        if not is_tv or not season:
            return True
        return int(season) in seasons
    except Exception as err:
        logger.debug(f"订阅存在性直查失败: {err}")
        return None


def is_subscribed(plugin: Any, mediainfo: Any, meta: Any, season: int) -> bool:
    """已订阅判定：优先直查订阅表/历史表，查不到该媒体时才回退 MP 原生 exists。"""
    is_tv = getattr(mediainfo, "type", None) == MediaType.TV
    state = find_subscription_state(mediainfo, season=season if is_tv else None, is_tv=is_tv)
    if state is not None:
        return state
    try:
        return bool(plugin.subscribechain.exists(mediainfo=mediainfo, meta=meta))
    except Exception as err:
        logger.debug(f"MP 订阅存在性判定失败: {err}")
        return False


def remember_subscribed(plugin: Any, sid: Any, tmdb_id: Any = None, season: Any = None) -> None:
    """持久化“该 Bangumi 条目已处理”，跨运行、跨重启幂等。"""
    if not sid:
        return
    data = plugin.get_data("subscribed") or {}
    data[f"bgm:{sid}"] = {
        "tmdb_id": tmdb_id,
        "season": season,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    plugin.save_data("subscribed", data)


def apply_subscribe_filter(plugin: Any, sub_id: int) -> None:
    """把插件配置的包含/排除规则写入新建订阅。"""
    try:
        from app.db import SessionFactory
        from app.db.models.subscribe import Subscribe

        db = SessionFactory()
        try:
            record = Subscribe.get(db, sub_id)
            if not record:
                return
            if plugin._include:
                record.include = plugin._include
            if plugin._exclude:
                record.exclude = plugin._exclude
            record.update(db=db, payload=record.to_dict())
        finally:
            db.close()
    except Exception as err:
        logger.debug(f"设置过滤规则跳过: {err}")
