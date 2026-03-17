# Reverse-Engineering Bilibili's Anti-Scraping System: A Technical Deep Dive

## Abstract

本文记录了一次针对 Bilibili（B站）视频平台反爬虫体系的逆向工程实践。起因是一位已注销账号的UP主的数千条视频面临"逻辑消失"——视频仍存在于服务器但无法通过正常界面访问。为完整归档这些视频的元数据，我逐一突破了 B站的 TLS 指纹检测、WBI 签名验证、分页硬限制等多层防护，最终成功爬取全部数据并生成可离线浏览的单文件网站。本文将详细拆解每一层防护的原理与绕过方法。

---

## 1. Background: The Problem of "Logical Deletion"

B站UP主注销账号后，其空间页返回 HTTP 404。但经过测试发现，这只是一层 UI 级别的"保护膜"——底层数据仍然完整：

- 视频可通过 `https://www.bilibili.com/video/BVxxxxx/` 正常播放
- 搜索 BV 号仍能找到视频
- 用户关系 API（粉丝数、关注数）仍返回有效数据
- 空间视频列表 API 依然可用

这意味着"注销"并非物理删除，而是逻辑屏蔽。但问题在于：**没有公开入口能浏览一个已注销用户的全部投稿列表**。如果视频数超过 3000 条，甚至连 API 也无法完整获取。

---

## 2. Bilibili's Multi-Layered Anti-Scraping Architecture

B站的反爬体系可以分为四层，每一层都需要不同的策略来应对：

```
┌───────────────────────────────────────────┐
│  Layer 4: Pagination Hard Limit (pn>100)  │  ← Server-side enforcement
├───────────────────────────────────────────┤
│  Layer 3: Rate Limiting (-799)            │  ← Request frequency control
├───────────────────────────────────────────┤
│  Layer 2: WBI Signature (-352)            │  ← API authentication
├───────────────────────────────────────────┤
│  Layer 1: TLS Fingerprinting (412)        │  ← Transport-layer detection
└───────────────────────────────────────────┘
```

### 2.1 Layer 1: TLS Fingerprinting (HTTP 412)

**Detection Mechanism**

B站在接入层部署了 TLS 指纹识别系统。当客户端发起 HTTPS 连接时，TLS 握手过程中的 Client Hello 报文包含大量可被指纹化的信息：

- 支持的密码套件列表及其顺序
- 支持的 TLS 扩展及其顺序
- 椭圆曲线参数
- 压缩方法

这些信息组合成所谓的 **JA3/JA4 指纹**。真实浏览器（Chrome、Firefox）与程序化 HTTP 客户端（Python `requests`、`curl`）的指纹存在显著差异。B站通过比对指纹来识别自动化请求，返回 HTTP 412。

**Observation**

```python
# 触发 412 的方式：
import requests
resp = requests.get("https://api.bilibili.com/x/space/wbi/arc/search?mid=<UID>")
# → HTTP 412

# 同样触发 412：
# curl "https://api.bilibili.com/..." → HTTP 412
```

Python 的 `requests` 库底层使用 `urllib3`，其 TLS 实现与 Chrome 的 BoringSSL 在握手行为上差异明显。这种差异在传输层就暴露了爬虫身份，甚至在 HTTP 请求发出之前。

**Solution: TLS Fingerprint Impersonation**

使用 `curl_cffi` 库可以精确模拟目标浏览器的 TLS 指纹：

```python
from curl_cffi import requests as cffi_requests

session = cffi_requests.Session(impersonate="chrome131")
resp = session.get("https://api.bilibili.com/x/space/wbi/arc/search?mid=<UID>")
# → HTTP 200 ✓
```

`curl_cffi` 基于 `curl-impersonate` 项目，它修改了 curl 的 TLS 引擎，使其生成与真实 Chrome 131 完全一致的 Client Hello 报文。

**A Counterintuitive Finding**

在实验中发现一个反直觉的现象：**不要预先访问 `bilibili.com` 获取 Cookie**。这与常规爬虫"先获取 Cookie 再请求"的做法相反。原因是 B站在 Cookie 中植入的 `buvid3` 等标识符会被关联到当前 TLS 会话，如果后续请求的 TLS 指纹发生变化（例如切换了库），反而会触发风控。直接以"裸"状态请求 API 更安全。

### 2.2 Layer 2: WBI Signature Verification (Error -352)

**Mechanism**

自 2023 年起，B站对空间视频列表等 API 引入了 **WBI 签名机制**。每个请求必须携带有效的 `w_rid`（签名）和 `wts`（时间戳），否则返回 `code: -352`（风控校验失败）。

**Reverse-Engineering the Signing Algorithm**

通过分析 B站前端 JavaScript，逆向出了完整的签名流程：

```
Step 1: 获取动态密钥
  GET /x/web-interface/nav
  → img_url: ".../7cd084941338484aae1ad9425b84077c.png"
  → sub_url: ".../4932caff0ff746eab6f01bf08b70ac45.png"

Step 2: 提取并混淆密钥
  raw_key = img_key + sub_key  (64 chars)
  mixin_key = PERMUTATION_TABLE.map(i => raw_key[i]).join("").slice(0, 32)

Step 3: 签名请求参数
  params.wts = current_timestamp
  sorted_query = sort_by_key(params).urlencode()
  w_rid = MD5(sorted_query + mixin_key)
```

其中 `PERMUTATION_TABLE` 是一个固定的 64 元素置换表，本质上是对原始密钥的字符重排：

```python
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]
```

这个置换表是硬编码在前端代码中的，但 `img_key` 和 `sub_key` 是动态生成的——B站会定期轮换这些密钥。

**Implementation**

```python
def get_mixin_key(orig: str) -> str:
    """Apply permutation table and truncate to 32 chars"""
    return "".join([orig[i] for i in MIXIN_KEY_ENC_TAB])[:32]

def sign_params(params: dict, mixin_key: str) -> dict:
    """Sign API parameters with WBI"""
    params["wts"] = str(int(time.time()))
    sorted_params = dict(sorted(params.items()))
    query = urllib.parse.urlencode(sorted_params)
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    sorted_params["w_rid"] = w_rid
    return sorted_params
```

**Key Refresh Strategy**

实验发现，长时间使用同一 `mixin_key` 签名会导致 `-352` 错误。解决方案是每 15~20 页重新请求 `/x/web-interface/nav` 获取新密钥：

```python
if page_counter >= 15:
    session, mixin_key = new_session_and_keys()
    page_counter = 0
```

### 2.3 Layer 3: Rate Limiting (Error -799)

**Mechanism**

B站对 API 调用频率进行限制。短时间内发出大量请求将收到 `code: -799`（请求过于频繁）。

**Solution**

在每次请求之间添加随机延迟：

```python
REQUEST_DELAY = (2.0, 3.5)  # seconds
time.sleep(random.uniform(*REQUEST_DELAY))
```

随机化延迟比固定间隔更能模拟真实用户行为。对于大量视频的爬取，整个过程需要数小时。

### 2.4 Layer 4: Pagination Hard Limit (pn > 100 → 412)

**The Hardest Problem**

这是最棘手的一层。B站在服务端硬编码了分页上限：**当 `pn`（页码）超过 100 时，无论 TLS 指纹多么完美、WBI 签名多么正确，都直接返回 HTTP 412**。

这意味着每种排序方式最多只能获取 100 × 30 = 3000 条记录。对于投稿数超过 3000 的UP主，这是一个无法从 API 层面绕过的硬限制。

**Root Cause Analysis: Not Anti-Scraping, But Architectural Constraint**

一个关键的观察：B站的视频合集（Series/Collection）功能，其**单个合集容纳的最大视频数恰好也是 3000**。这与分页限制 100 页 × 30 条/页 = 3000 完全吻合。这不太可能是巧合——它强烈暗示 **3000 是 B站底层架构中的一个共享常量**，而非仅仅是一个反爬策略。

这个限制很可能根植于 B站后端的数据存储和查询层。以下是几种可能的源码级原因：

**(1) Elasticsearch `max_result_window` 限制**

B站的视频搜索服务大概率基于 Elasticsearch（或类似的搜索引擎）。ES 有一个核心参数 `max_result_window`，它限制了 `from + size` 的最大值（默认为 10,000）。B站很可能将其配置为 3000：

```yaml
# Elasticsearch index settings (推测)
index.max_result_window: 3000
```

```java
// 后端 Java/Go 服务中的参数校验 (推测)
public static final int MAX_PAGE = 100;
public static final int PAGE_SIZE = 30;
public static final int MAX_RESULT_WINDOW = MAX_PAGE * PAGE_SIZE;  // 3000

if (pn > MAX_PAGE || pn * ps > MAX_RESULT_WINDOW) {
    return ResponseEntity.status(412).build();
}
```

**为什么 ES 要有这个限制？** 因为 ES 的分页采用 `from + size` 机制（类似 SQL 的 `OFFSET + LIMIT`）。当 `from` 很大时，ES 需要在每个分片上获取 `from + size` 条结果，然后在协调节点上合并排序后丢弃前 `from` 条。如果集群有 5 个分片：

```
查第 1 页:   每个分片取 30 条  → 协调节点排序 150 条  → 返回前 30 条
查第 100 页: 每个分片取 3000 条 → 协调节点排序 15,000 条 → 返回第 2971~3000 条
查第 1000 页: 每个分片取 30,000 条 → 协调节点排序 150,000 条 → 返回第 29,971~30,000 条 ❌ OOM
```

深度分页的内存开销随页码线性增长，对集群稳定性构成威胁。3000 是一个在"用户体验"和"系统负载"之间的工程折中。

**(2) 数据库 OFFSET 性能悬崖**

即使 B站部分数据使用 MySQL/TiDB 存储，深度分页同样面临性能问题：

```sql
-- 第 1 页: 快速
SELECT * FROM videos WHERE mid = ? ORDER BY pubdate DESC LIMIT 30 OFFSET 0;

-- 第 100 页: 还可以
SELECT * FROM videos WHERE mid = ? ORDER BY pubdate DESC LIMIT 30 OFFSET 2970;

-- 第 1000 页: 灾难性慢
SELECT * FROM videos WHERE mid = ? ORDER BY pubdate DESC LIMIT 30 OFFSET 29970;
-- MySQL 需要扫描并丢弃前 29,970 行，然后返回 30 行
```

`OFFSET` 的时间复杂度是 O(offset + limit)，而非 O(limit)。对于高投稿量UP主，深度分页可能触发慢查询，甚至导致数据库连接池耗尽。

**(3) 统一的业务层常量**

最可能的实现是，B站在后端服务的业务层定义了一个统一的常量，被多个功能复用：

```go
// 推测的 Go 后端常量定义
package constants

const (
    MaxPageSize      = 30
    MaxPageNum       = 100
    MaxResultWindow  = MaxPageNum * MaxPageSize  // 3000
)
```

这个常量同时约束了：
- 空间视频列表 API 的分页上限 → `pn ≤ 100`
- 合集的最大视频数 → `count ≤ 3000`
- 可能还包括搜索结果、收藏夹等场景

**从 412 而非业务错误码可以进一步推断**：这个检查很可能发生在 **API 网关层**（如 Nginx/OpenResty/自研网关），而非业务服务内部。业务服务通常返回 JSON 格式的错误码（如 -352、-799），而 412 是一个 HTTP 状态码，更像是网关级别的拦截。这意味着分页限制可能配置在网关的 WAF 规则或中间件中：

```lua
-- OpenResty/Nginx Lua 层的参数校验 (推测)
local pn = tonumber(ngx.var.arg_pn) or 1
if pn > 100 then
    return ngx.exit(412)
end
```

**Summary: 3000 is a System-Wide Architectural Constant**

综合以上分析，100 页限制并非单纯的反爬策略，而是一个**系统级的架构约束**，源于深度分页在分布式搜索引擎和数据库中的固有性能问题。B站选择 3000 作为上限，并将其统一应用到多个业务场景（API 分页、合集容量），是一个典型的**防御性工程决策**——牺牲极少数超高产UP主在 3000 条以后的可访问性，换取整个系统的稳定性和可预测性。

**Solution: Multi-Sort-Order Union Strategy**

B站的视频搜索 API 支持多种排序方式。不同排序方式下，视频的分页位置不同。利用这一点，可以通过多种排序分别爬取、去重合并来扩大覆盖范围：

| Sort Order | 含义 | 获取到的视频 |
|------------|------|-------------|
| `pubdate` | 发布时间 | 最新 3000 条 |
| `click` | 播放量 | 最热 3000 条 |
| `stow` | 收藏量 | 收藏最多 3000 条 |

三种排序的并集可以覆盖大部分视频。在实际测试中，对于投稿数超过 5000 的UP主，三种排序合计约覆盖了 3000~4000+ 条不重复视频。

```python
sort_orders = ["pubdate", "click", "stow"]
all_videos_map = {}  # bvid → video, for deduplication

for order in sort_orders:
    new_videos = fetch_all_with_order(order, existing_bvids, progress)
    for v in new_videos:
        all_videos_map[v["bvid"]] = v  # dedup by BV number
```

**Solution for Remaining Pages: Browser Console Injection**

对于多排序合并后仍无法覆盖的视频（即第 101 页以后的时间线数据），需要借助**真实浏览器环境**。在已登录的浏览器中，分页限制可能有所放宽（或者 Cookie 中的凭证可以绕过部分检测）。

为此，我编写了一段可直接粘贴到浏览器 Console 中执行的 JavaScript：

```javascript
(async function() {
    const MID = "<TARGET_UID>";
    const START_PAGE = 101;
    const END_PAGE = 200;   // ceil(totalVideos / 30)

    // ... WBI signing (including a pure-JS MD5 implementation) ...

    for (let pn = START_PAGE; pn <= END_PAGE; pn++) {
        let params = { mid: MID, ps: "30", pn: pn.toString(), order: "pubdate" };
        let queryStr = signParams(params);
        let resp = await fetch(url, { credentials: "include" });
        // ... collect results ...
        await new Promise(r => setTimeout(r, 1200));
    }

    // Auto-download as JSON
    let blob = new Blob([JSON.stringify(allVideos)], {type: "application/json"});
    // ... trigger download ...
})();
```

这个脚本的关键设计决策：
- **纯 JavaScript MD5 实现**：浏览器环境中没有 `hashlib`，需要在脚本内内联一个完整的 MD5 算法
- **`credentials: "include"`**：携带浏览器 Cookie，利用已登录状态
- **自动下载**：完成后自动生成 JSON 文件并触发下载，无需手动复制数据

---

## 3. Data Pipeline: From Raw API to Self-Contained Archive

### 3.1 Pipeline Overview

```
API Endpoints                    Processing                    Output
─────────────                    ──────────                    ──────
/x/space/wbi/arc/search  ──→  Python Scraper  ──→  CSV (metadata)
     ↓                              ↓
/x/web-interface/nav     ──→  WBI Key Refresh      Cover Cache (base64)
     ↓                              ↓
Browser Console          ──→  JSON (pages 101+)     Banner/Avatar (base64)
                                    ↓
                              HTML Generator  ──→  Self-Contained HTML
                                                   (single file, ~18MB)
```

### 3.2 Image Compression for Embedding

为了生成**单文件自包含 HTML**，所有图片必须以 base64 编码内嵌。数千张封面如果不压缩，HTML 将超过数百 MB。压缩策略如下：

```python
def compress_image(img_data: bytes, max_kb: float = 2.5) -> str:
    img = Image.open(io.BytesIO(img_data)).convert("RGB")
    img = img.resize((160, int(160 * img.height / img.width)), Image.LANCZOS)

    for quality in [60, 45, 30, 20, 15, 10, 5]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_kb * 1024:
            return base64.b64encode(buf.getvalue()).decode("ascii")
```

每张封面缩放到宽 160px，逐步降低 JPEG 质量直到文件大小低于 2.5KB。最终数千张封面总计约 10MB base64 数据。

### 3.3 Deduplication Strategy

多排序方式和手动爬取的数据必然存在重复。以 BV 号（Bilibili 视频唯一标识符）为 key 进行去重：

```python
all_videos_map = {}  # bvid → video_dict
for v in videos_from_all_sources:
    all_videos_map[v["bvid"]] = v  # later entries overwrite earlier ones
```

### 3.4 Resilience: Progress Tracking and Resume

大量视频的爬取需要数小时，网络中断或风控触发随时可能发生。实现了断点续传机制：

```python
# Save progress after each page
progress[f"last_page_{order}"] = page
save_progress(progress)  # writes to progress.json

# On restart, resume from last successful page
start_page = progress.get(f"last_page_{order}", 0) + 1
```

---

## 4. Frontend: Replicating the Bilibili Space Page

最终的 HTML 成品不是一个简单的数据表格，而是一个高保真的 B站空间页复刻，支持：

- **响应式布局**：桌面端 5 列网格，移动端 2 列
- **搜索与排序**：实时搜索（300ms 防抖）、按时间/播放量/收藏量排序
- **分页系统**：每页 30 条，带智能页码按钮
- **设备自适应交互**：
  - 桌面端点击 → 跳转 B站播放
  - 移动端点击 → 弹出 BV 号供复制（因为手机浏览器打开 file:// 无法跳转 B站 App）
- **视觉还原**：毛玻璃（Glassmorphism）效果、渐变横幅、圆角头像

### 4.1 Mobile Clipboard Challenge

在移动端通过 `file://` 协议打开 HTML 时，`navigator.clipboard.writeText()` 会因安全策略限制而失败（该 API 要求 Secure Context，即 HTTPS 或 localhost）。

进一步测试发现，`document.execCommand("copy")` 在部分移动端浏览器上虽然返回 `true`，但实际并未写入剪贴板——是一个 **false positive**。

最终采用的分级策略：

```javascript
function doCopy(bv) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        // Modern API (works on HTTPS)
        navigator.clipboard.writeText(bv)
            .then(() => showModal(bv))
            .catch(() => showModal(bv, "select"));  // fallback on failure
    } else if (isMobile) {
        // Mobile file:// — skip unreliable execCommand, show selectable input
        showModal(bv, "select");
    } else {
        // Desktop fallback
        var ta = document.createElement("textarea");
        ta.value = bv;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        showModal(bv);
    }
}
```

"select" 模式会弹出一个包含 BV 号的 `<input>` 元素，文本自动选中，用户长按即可看到系统原生的"拷贝"菜单。这是在 `file://` 协议下最可靠的方案。

---

## 5. Results

在一次实际爬取中的结果：

| Metric | Value |
|--------|-------|
| API 爬取（前100页 × 3种排序） | ~3,000~4,200 (去重后) |
| 浏览器手动爬取（101+页） | 视UP主投稿量而定 |
| 封面图片 | 压缩至 ≤2.5KB/张 |
| 最终 HTML 大小 | ~15~20 MB |
| 爬取总耗时 | ~2~3 小时（API） + ~数分钟（浏览器） |

---

## 6. Lessons Learned

### 6.1 TLS Fingerprinting is the New Frontier

传统的反爬措施（User-Agent 检测、Cookie 验证、IP 限制）都在应用层。TLS 指纹检测将战场推到了传输层，这使得大多数 HTTP 库在连接建立阶段就暴露了身份。`curl_cffi` / `curl-impersonate` 是目前最优雅的解决方案，但这本质上是一场持续的军备竞赛。

### 6.2 Server-Side Pagination Limits are Effective

B站的 100 页硬限制是本项目中最难突破的防线。它不依赖客户端行为检测，而是在服务端直接截断——无论请求多么"合法"，`pn > 100` 就返回 412。这种策略简单粗暴但极其有效，迫使我不得不切换到完全不同的技术路径（浏览器控制台手动操作）。

### 6.3 Defense in Depth Works

B站的四层防护互相独立、逐层递进。突破了 TLS 指纹还要面对 WBI 签名，通过了签名还有频率限制，绕过了频率限制还有分页硬限制。每一层都提高了攻击成本，四层叠加使得全自动化爬取变得不可能——最终不得不引入人工操作环节。这是**纵深防御（Defense in Depth）**理念的实际体现。

### 6.4 The "Logical Deletion" Problem

从用户视角看，注销后视频"消失"了。但从技术角度看，数据仍然完整存在，只是缺少索引入口。这种设计可能是出于存储成本考虑（删除视频文件成本高），但也意味着"注销"并不等于"数据删除"。这在隐私保护（如 GDPR 的"被遗忘权"）语境下值得深思。

---

## 7. Tech Stack

| Component | Technology | Role |
|-----------|-----------|------|
| HTTP Client | `curl_cffi` (Python) | TLS fingerprint impersonation |
| Image Processing | `Pillow` | Cover compression to base64 |
| Signing | `hashlib` (Python) / Pure JS MD5 | WBI signature generation |
| Browser Automation | Vanilla JavaScript (Console) | Bypass pagination limit |
| Frontend | Single-file HTML/CSS/JS | Offline-capable archive viewer |
| Data Format | CSV + JSON | Intermediate data exchange |

---

## 8. Ethical Considerations

本项目的目的是为已注销UP主的公开视频建立个人存档。所有被爬取的数据（视频标题、播放量、封面等）均为公开信息，可通过浏览器正常访问。爬取过程中严格控制请求频率（2~3.5 秒间隔），以避免对 B站服务器造成负担。最终产物仅用于个人纪念用途，不涉及商业目的。

关于 robots.txt 合规性：B站的 `robots.txt`（`www.bilibili.com`）中的规则适用于网页爬虫，而本项目调用的是 `api.bilibili.com` 的 JSON API（不同子域名），且行为上是 API 客户端而非搜索引擎爬虫，因此不在 robots.txt 的适用范围内。

---

## References

- [curl-impersonate: A special build of curl that can impersonate browsers](https://github.com/lwthiker/curl-impersonate)
- [Bilibili WBI Signature Documentation (Community)](https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html)
- [JA3 - A method for profiling SSL/TLS Clients](https://github.com/salesforce/ja3)
- [Elasticsearch: Paginate search results](https://www.elastic.co/guide/en/elasticsearch/reference/current/paginate-search-results.html)
