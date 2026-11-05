"""Vuetify UI rendering for BangumiRank."""

from typing import Any, Dict, List, Tuple


class BangumiUI:
    @staticmethod
    def render_form() -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    # 1. 核心运行与模式
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件", "color": "primary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "auto_subscribe", "label": "自动创建订阅", "hint": "关闭时新番进入待确认候选列表", "persistent-hint": True, "color": "info"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "保存后立即运行一次", "color": "warning"}}]},
                    ]},
                    # 2. 账号凭据与网络
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 7}, "content": [{
                            "component": "VTextField",
                            "props": {
                                "model": "token",
                                "label": "Bangumi Access Token",
                                "type": "password",
                                "prepend-inner-icon": "mdi-key-variant",
                                "hint": "免申请1键生成: https://next.bgm.tv/demo/access-token",
                                "persistent-hint": True,
                            }
                        }]},
                        {"component": "VCol", "props": {"cols": 12, "md": 5}, "content": [{
                            "component": "VTextField",
                            "props": {
                                "model": "proxy",
                                "label": "自定义代理",
                                "placeholder": "http://127.0.0.1:7890",
                                "prepend-inner-icon": "mdi-lan",
                                "hint": "网络超时时填写，留空走直连或系统代理",
                                "persistent-hint": True,
                            }
                        }]},
                    ]},
                    # 3. 联动与同步设置
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VSwitch", "props": {"model": "sync_mp_subscribe", "label": "MP 订阅反向在 Bangumi 标记在看", "hint": "在 MoviePilot 探索或搜索订阅番剧时自动标记", "persistent-hint": True, "color": "success"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "cron", "label": "定时周期 Cron", "placeholder": "0 8 * * *", "prepend-inner-icon": "mdi-clock-outline"}}]},
                    ]},
                    # 4. 抓取偏好
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "sync_wish", "label": "同步个人想看 (Wish)", "color": "secondary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VSwitch", "props": {"model": "sync_do", "label": "同步个人在看 (Do)", "color": "secondary"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "wish_top", "label": "拉取条数上限", "placeholder": "20", "type": "number"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [{"component": "VTextField", "props": {"model": "min_score", "label": "最低评分门槛", "placeholder": "0 为不限", "type": "number"}}]},
                    ]},
                    # 5. 过滤与高级
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "include", "label": "包含关键字", "placeholder": "仅保留匹配的标题"}}]},
                        {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [{"component": "VTextField", "props": {"model": "exclude", "label": "排除关键字", "placeholder": "过滤掉匹配的标题"}}]},
                    ]},
                    {"component": "VRow", "content": [
                        {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VSwitch", "props": {"model": "clear", "label": "保存时清空历史与候选队列", "color": "error"}}]},
                    ]},
                ]
            }
        ], {
            "enabled": False, "auto_subscribe": False, "token": "", "proxy": "", "use_system_proxy": False,
            "cron": "0 8 * * *", "onlyonce": False, "sync_wish": True, "sync_do": False,
            "wish_top": 20, "min_score": 0.0, "sync_mp_subscribe": True,
            "include": "", "exclude": "", "clear": False,
        }

    @staticmethod
    def render_page(user_info: dict, candidates: List[dict], history: List[dict], auto_subscribe: bool) -> List[dict]:
        elements = []

        # 1. 顶部账号卡片
        if user_info and user_info.get("id"):
            avatar = (user_info.get("avatar") or {}).get("large") or ""
            elements.append({
                "component": "VCard",
                "props": {"class": "mb-4 pa-4 rounded-lg", "variant": "tonal", "color": "primary"},
                "content": [
                    {"component": "div", "props": {"class": "d-flex align-center justify-space-between flex-wrap ga-3"}, "content": [
                        {"component": "div", "props": {"class": "d-flex align-center ga-3"}, "content": [
                            {"component": "VAvatar", "props": {"image": avatar, "size": 48, "class": "elevation-2"}} if avatar else {"component": "span"},
                            {"component": "div", "content": [
                                {"component": "div", "props": {"class": "text-h6 font-weight-bold d-flex align-center ga-2"}, "content": [
                                    {"component": "span", "text": str(user_info.get("nickname") or "Bangumi 用户")},
                                    {"component": "VChip", "props": {"size": "x-small", "color": "success", "variant": "flat"}, "text": "API 已连接"},
                                ]},
                                {"component": "div", "props": {"class": "text-caption opacity-80 mt-1"}, "text": f"UID: {user_info.get('id')} · @{user_info.get('username')} · 官方开放 API 直连"},
                            ]}
                        ]},
                        {"component": "div", "content": [
                            {"component": "VChip", "props": {
                                "color": "info" if auto_subscribe else "warning",
                                "variant": "elevated",
                                "prepend-icon": "mdi-robot" if auto_subscribe else "mdi-account-eye",
                            }, "text": "模式: 自动订阅" if auto_subscribe else "模式: 手动候选审核"}
                        ]}
                    ]}
                ]
            })
        else:
            elements.append({
                "component": "VAlert",
                "props": {
                    "type": "warning",
                    "variant": "tonal",
                    "class": "mb-4 rounded-lg",
                    "title": "未绑定 Bangumi 账号",
                    "text": "请在插件设置中填入 Access Token (可在 https://next.bgm.tv/demo/access-token 免申请1键获取)。",
                }
            })

        # 2. 待确认候选番剧区
        if candidates:
            candidate_cols = []
            for c in candidates:
                cand_id = c.get("candidate_id")
                poster = c.get("poster") or "https://raw.githubusercontent.com/honue/MoviePilot-Plugins/main/icons/miku.jpg"
                bgm_title = str(c.get("bgm_title") or "未知番剧")
                score = str(c.get("score") or "暂无")
                tmdb_title = str(c.get("tmdb_title") or "")
                year = str(c.get("year") or "")
                season = str(c.get("season") or "1")
                bgm_link = c.get("bgm_link") or "#"

                card = {
                    "component": "VCard",
                    "props": {
                        "class": "rounded-lg overflow-hidden h-100",
                        "variant": "elevated",
                        "elevation": 2,
                    },
                    "content": [
                        {"component": "div", "props": {"class": "d-flex h-100"}, "content": [
                            # 左侧大封面
                            {"component": "div", "props": {"class": "flex-shrink-0", "style": "width: 104px; min-height: 148px;"}, "content": [
                                {"component": "VImg", "props": {
                                    "src": poster,
                                    "height": "100%",
                                    "cover": True,
                                    "class": "h-100",
                                }}
                            ]},
                            # 右侧详情与操作
                            {"component": "div", "props": {"class": "pa-3 flex-grow-1 d-flex flex-column justify-space-between min-width-0"}, "content": [
                                # 头部标题与评分
                                {"component": "div", "content": [
                                    {"component": "div", "props": {"class": "d-flex align-center justify-space-between ga-2 mb-1"}, "content": [
                                        {"component": "a", "props": {
                                            "href": bgm_link,
                                            "target": "_blank",
                                            "class": "text-subtitle-1 font-weight-bold text-truncate text-decoration-none text-high-emphasis",
                                            "style": "max-width: calc(100% - 60px);",
                                        }, "text": bgm_title},
                                        {"component": "VChip", "props": {
                                            "size": "x-small",
                                            "color": "amber-darken-2",
                                            "variant": "tonal",
                                            "prepend-icon": "mdi-star",
                                        }, "text": score},
                                    ]},
                                    # 来源标签
                                    {"component": "div", "props": {"class": "mb-2"}, "content": [
                                        {"component": "VChip", "props": {"size": "x-small", "color": "secondary", "variant": "tonal", "class": "mr-1"}, "text": c.get("source", "想看")},
                                        {"component": "span", "props": {"class": "text-caption text-medium-emphasis"}, "text": f"发现于 {c.get('add_time', '')[:10]}"},
                                    ]},
                                    # TMDb 识别信息卡片条
                                    {"component": "div", "props": {
                                        "class": "text-body-2 font-weight-medium px-2 py-1 rounded bg-surface-variant d-flex align-center ga-1 text-truncate",
                                    }, "content": [
                                        {"component": "span", "props": {"class": "text-primary font-weight-bold"}, "text": "🎬 TMDb:"},
                                        {"component": "span", "props": {"class": "text-truncate"}, "text": f"{tmdb_title} ({year}) 第{season}季"},
                                    ]},
                                ]},
                                # 底部按钮条
                                {"component": "div", "props": {"class": "d-flex align-center ga-2 mt-2 pt-2 border-t"}, "content": [
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "color": "primary",
                                            "size": "small",
                                            "variant": "flat",
                                            "prepend-icon": "mdi-plus-box",
                                            "class": "flex-grow-1",
                                        },
                                        "text": "选定订阅",
                                        "events": {"click": {"api": "plugin/BangumiCompanion/subscribe_candidate", "method": "get", "params": {"candidate_id": cand_id}}},
                                    },
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "color": "default",
                                            "size": "small",
                                            "variant": "text",
                                            "prepend-icon": "mdi-eye-off-outline",
                                        },
                                        "text": "忽略",
                                        "events": {"click": {"api": "plugin/BangumiCompanion/ignore_candidate", "method": "get", "params": {"candidate_id": cand_id}}},
                                    },
                                ]}
                            ]}
                        ]}
                    ]
                }
                candidate_cols.append({"component": "VCol", "props": {"cols": 12, "md": 6, "xl": 4}, "content": [card]})

            elements.append({
                "component": "div",
                "props": {"class": "mb-5"},
                "content": [
                    # 候选区标题与全局按钮
                    {"component": "div", "props": {"class": "d-flex justify-space-between align-center mb-3 flex-wrap ga-2"}, "content": [
                        {"component": "div", "props": {"class": "d-flex align-center ga-2"}, "content": [
                            {"component": "div", "props": {"class": "text-h6 font-weight-bold"}, "text": "待确认候选"},
                            {"component": "VChip", "props": {"color": "primary", "size": "small", "variant": "flat"}, "text": str(len(candidates))},
                        ]},
                        {"component": "div", "props": {"class": "d-flex align-center ga-2"}, "content": [
                            {
                                "component": "VBtn",
                                "props": {
                                    "color": "success",
                                    "size": "small",
                                    "variant": "tonal",
                                    "prepend-icon": "mdi-playlist-check",
                                },
                                "text": "一键全订",
                                "events": {"click": {"api": "plugin/BangumiCompanion/subscribe_all_candidates", "method": "get"}},
                            },
                            {
                                "component": "VBtn",
                                "props": {
                                    "color": "error",
                                    "size": "small",
                                    "variant": "text",
                                    "prepend-icon": "mdi-trash-can-outline",
                                },
                                "text": "清空候选",
                                "events": {"click": {"api": "plugin/BangumiCompanion/clear_candidates", "method": "get"}},
                            },
                        ]},
                    ]},
                    # 卡片网格
                    {"component": "VRow", "content": candidate_cols},
                ]
            })

        # 3. 历史与双向联动流水
        if history:
            history_rows = []
            for h in history[:30]:
                tag_color = "primary"
                cat = str(h.get("type") or "")
                if "在看" in cat:
                    tag_color = "success"
                elif "打格子" in cat or "已看" in cat:
                    tag_color = "info"
                elif "忽略" in cat:
                    tag_color = "grey"

                history_rows.append({
                    "component": "VCard",
                    "props": {"class": "mb-2 pa-2 rounded-lg", "variant": "outlined"},
                    "content": [
                        {"component": "div", "props": {"class": "d-flex align-center justify-space-between ga-3"}, "content": [
                            {"component": "div", "props": {"class": "d-flex align-center ga-3 min-width-0"}, "content": [
                                {"component": "VImg", "props": {
                                    "src": h.get("poster") or "",
                                    "width": 36,
                                    "height": 50,
                                    "cover": True,
                                    "class": "rounded flex-shrink-0",
                                }},
                                {"component": "div", "props": {"class": "min-width-0"}, "content": [
                                    {"component": "a", "props": {
                                        "href": h.get("bangumi_link") or "#",
                                        "target": "_blank",
                                        "class": "font-weight-medium text-decoration-none text-high-emphasis text-truncate d-block",
                                    }, "text": str(h.get("title") or "番剧")},
                                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis mt-1"}, "text": str(h.get("time") or "")},
                                ]}
                            ]},
                            {"component": "VChip", "props": {
                                "color": tag_color,
                                "size": "small",
                                "variant": "tonal",
                                "class": "flex-shrink-0",
                            }, "text": cat}
                        ]}
                    ]
                })

            elements.append({
                "component": "div",
                "props": {"class": "mt-4"},
                "content": [
                    {"component": "div", "props": {"class": "text-subtitle-1 font-weight-bold mb-2 d-flex align-center ga-2"}, "content": [
                        {"component": "span", "text": "双向联动记录"},
                        {"component": "VChip", "props": {"size": "x-small", "color": "default", "variant": "tonal"}, "text": str(len(history))},
                    ]},
                    {"component": "div", "content": history_rows},
                ]
            })
        elif not candidates:
            elements.append({
                "component": "VCard",
                "props": {"class": "text-center pa-8 rounded-lg", "variant": "tonal"},
                "content": [
                    {"component": "div", "props": {"class": "text-h6 font-weight-bold mb-1"}, "text": "暂无待确认候选番剧"},
                    {"component": "div", "props": {"class": "text-caption text-medium-emphasis"}, "text": "可在设置中勾选【保存后立即运行一次】拉取您的个人想看/在看条目"},
                ]
            })

        return elements
