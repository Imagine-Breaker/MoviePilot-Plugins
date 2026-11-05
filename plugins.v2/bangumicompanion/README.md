# Bangumi 追番伴侣 (BangumiRank) v1.0.0

基于 MoviePilot 架构深度重构的 Bangumi 个人追番与双向联动插件。

全面转向 **Bangumi 官方开放 API (v0)**，专注个人番剧管理：**想看/在看候选审核** 与 **MP 订阅反向同步在看**，提供极致精美的现代自适应海报卡片与严谨的 TV 动漫防误识机制。

---

## 🌟 核心特性

1. **官方 API 直连 & 账号鉴权**：
   - 直接与 `api.bgm.tv` 通信，稳定高效。
   - 配置个人 Access Token，启动自动校验账号信息并在插件看板显示个人头像与 UID。
   - 支持自定义 HTTP/SOCKS 代理或沿用 MoviePilot 系统全局代理。
2. **候选审核机制与全局自动开关**：
   - **全局自动开关**：支持设置“自动添加订阅”。
     - 开启：识别 TMDb 成功后直接全自动下发订阅任务；
     - 关闭（默认推荐）：识别结果进入**【待确认候选】**卡片队列，供人工校验确认。
   - **自适应横版海报卡片**：
     - 现代响应式自适应网格，移动端单列、桌面端多列。
     - 2:3 黄金比例大封面海报、评分徽章、首播年份、中日双语对照、TMDb 识别结果标签。
     - 支持**单个选定订阅**、**单个忽略**、**一键全订**与**清空候选**。
3. **高精准动漫识别（彻底杜绝真人版电影误识）**：
   - **Bangumi ID 直连**：优先使用 MoviePilot 官方内置的 Bangumi ↔ TMDb 1:1 映射库。
   - **类型强制推导**：针对 TV/Web/OVA 或多集番剧，强制锁定 `mtype=MediaType.TV`，物理封死电影搜索。
   - **动画分类校验**：强制校验 TMDb 动画类型（Genre 16），坚决剔除重名真人版影视。
4. **MP 订阅反向标在看**：
   - 无论在插件候选卡片、MoviePilot 探索页、榜单还是搜索框订阅动漫，均会自动在您的 Bangumi 账号反向标记为“在看”。
5. **安全与稳定性**：
   - 前端所有 API 显式配置 `auth="bear"`，杜绝因鉴权失败被踢回登录页。
   - 移除高风险的播放自动打格子功能，杜绝因 TMDb/BGM 集数与分季不一致导致个人观剧历史被乱标。

---

## 🚀 本地安装方法

### 方法一：直接复制目录到 MoviePilot
将 `plugins/bangumirank` 文件夹复制或挂载到 MoviePilot 的插件目录：
* Docker 默认路径：`/app/app/plugins/bangumirank` 或挂载卷 `/config/plugins/bangumirank`
* 重启 MoviePilot 容器或在插件管理中重新加载。

### 方法二：使用本地插件路径（开发调试）
在 MoviePilot 的环境变量中添加：
```bash
PLUGIN_LOCAL_REPO_PATHS=/path/to/MoviePilot-Plugins
PLUGIN_AUTO_RELOAD=true
```

---

## ⚙️ 配置说明

1. **获取 Bangumi Access Token**：
   - 打开 [Bangumi 开发者管理平台](https://bgm.tv/dev/app)；
   - 点击“创建应用”或直接生成 Personal Access Token；
   - 复制 Token 并粘贴到插件设置的 `Bangumi Access Token` 输入框中。
2. **网络代理配置**：
   - 如果您的网络直连 Bangumi API 受限，可勾选“使用系统代理”，或在“自定义代理”中填入例如 `http://127.0.0.1:7890`。
3. **播放打格子设置**：
   - 开启“播放完成自动打格子”；
   - 若多个用户使用媒体服务器，可在“同步的用户白名单”填入您的用户名（以逗号分隔），避免其他家庭成员的播放污染您的 Bangumi 进度。
