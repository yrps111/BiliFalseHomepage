# Bilibili Video Archiver | B站UP主视频存档工具

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### What is this?

A complete toolkit for archiving any Bilibili (B站) content creator's video metadata into a **single self-contained HTML file** that works offline on any device.

This project reverse-engineers Bilibili's multi-layered anti-scraping system, including TLS fingerprint detection, WBI signature verification, rate limiting, and pagination hard limits.

### Features

- **TLS Fingerprint Bypass** — Uses `curl_cffi` to impersonate Chrome 131's TLS handshake
- **WBI Signature** — Full implementation of Bilibili's proprietary API signing algorithm
- **100-Page Limit Workaround** — Multi-sort-order union strategy + browser console injection
- **Self-Contained HTML Output** — All cover images compressed to base64 and embedded inline
- **Bilibili Space Page Replica** — Glassmorphism UI, search, sort, pagination, responsive design
- **Mobile-Friendly** — Device-aware interactions (desktop: click to jump; mobile: click to copy BV number)

### Files

| File | Description |
|------|-------------|
| `bilibili_scraper.py` | Main Python scraper (pages 1-100, 3 sort orders) |
| `browser_fetch.js` | Browser console script (pages 101+, bypasses pagination limit) |
| `generate_html.py` | HTML generator (CSV + covers → single-file website) |
| `B站视频爬取研究.md` | Technical deep dive (blog post) |
| `操作指南.md` | Step-by-step operation guide |

### Quick Start

```bash
pip install curl_cffi Pillow
```

1. Edit `bilibili_scraper.py`, set `TARGET_MID = <target UID>`
2. Run `python bilibili_scraper.py`
3. (Optional) For 101+ pages: paste `browser_fetch.js` in browser console
4. Edit `generate_html.py`, set `UP_NAME` and `UP_UID`
5. Run `python generate_html.py`

### Technical Blog Post

See [B站视频爬取研究.md](B站视频爬取研究.md) for a detailed analysis of Bilibili's 4-layer anti-scraping architecture, including:
- TLS fingerprinting (JA3/JA4) and how to bypass it
- WBI signature algorithm reverse-engineering
- Root cause analysis of the 3000-video limit (Elasticsearch `max_result_window`, DB OFFSET performance, unified business constants)
- Mobile clipboard API challenges under `file://` protocol

### License & Attribution

**Author**: [yrps111](https://github.com/yrps111)

- You are free to use and adapt this project for personal and educational purposes
- **Attribution required**: If you use this project or its code, please credit the original source with a link to this repository
- **Derivative works allowed**: You may create derivative works based on this project, with proper attribution
- **No plagiarism**: Do not claim this work as your own. Copying without attribution is prohibited

---

<a id="中文"></a>

## 中文

### 这是什么？

一套完整的B站UP主视频存档工具，可以将任意UP主的全部视频元数据爬取下来，生成一个**单文件自包含HTML**，在任何设备上离线浏览。

本项目对B站的多层反爬体系进行了逆向工程，包括 TLS 指纹检测、WBI 签名验证、频率限制和分页硬限制。

### 功能特性

- **TLS 指纹绕过** — 使用 `curl_cffi` 模拟 Chrome 131 的 TLS 握手
- **WBI 签名** — 完整实现 B站私有的 API 签名算法
- **100页限制突破** — 多排序并集策略 + 浏览器控制台注入
- **单文件HTML输出** — 所有封面压缩为 base64 内嵌
- **仿B站空间页** — 毛玻璃UI、搜索、排序、分页、响应式设计
- **手机适配** — 设备自适应交互（电脑：点击跳转；手机：点击复制BV号）

### 文件说明

| 文件 | 说明 |
|------|------|
| `bilibili_scraper.py` | 主爬虫（前100页，3种排序） |
| `browser_fetch.js` | 浏览器控制台脚本（101页以后，突破分页限制） |
| `generate_html.py` | HTML生成器（CSV+封面 → 单文件网站） |
| `B站视频爬取研究.md` | 技术深度分析（博客文章） |
| `操作指南.md` | 操作流程指南 |

### 快速开始

```bash
pip install curl_cffi Pillow
```

1. 编辑 `bilibili_scraper.py`，设置 `TARGET_MID = 目标UID`
2. 运行 `python bilibili_scraper.py`
3. （可选）如需101页以后的数据：在浏览器控制台粘贴 `browser_fetch.js`
4. 编辑 `generate_html.py`，设置 `UP_NAME` 和 `UP_UID`
5. 运行 `python generate_html.py`

### 技术博客

详见 [B站视频爬取研究.md](B站视频爬取研究.md)，包含对B站四层反爬架构的详细分析：
- TLS 指纹识别（JA3/JA4）及绕过方法
- WBI 签名算法逆向
- 3000条视频限制的根因分析（ES `max_result_window`、数据库 OFFSET 性能、统一业务常量）
- 移动端 `file://` 协议下的剪贴板 API 挑战

### 使用许可

**作者**: [yrps111](https://github.com/yrps111)

- 本项目可自由用于个人和教育用途
- **须注明出处**：如使用本项目或其代码，请标明原作者并附上本仓库链接
- **允许二创**：可以基于本项目进行二次创作，但须标明出处
- **禁止盗用**：不得将本项目据为己有，禁止未标注出处的复制行为
