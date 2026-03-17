"""
B站UP主视频存档 — HTML生成器
读取CSV数据 + 封面缓存，生成仿B站空间页风格的单文件自包含HTML

用法:
    1. 先运行 bilibili_scraper.py 获取CSV和封面缓存
    2. 准备 banner_b64.txt 和 avatar_b64.txt（可选）
    3. 修改下方配置
    4. python generate_html.py
"""
import csv, json, os, sys

# ============ 配置（修改此处） ============
UP_NAME = "UP主名称"        # ← 替换为UP主昵称
UP_UID = "0"                # ← 替换为UP主UID
UP_SIGN = "这个人很懒，什么都没写"  # ← UP主签名/简介

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, f"videos_{UP_UID}.csv")
COVER_CACHE = os.path.join(SCRIPT_DIR, "cover_cache.json")
HTML_FILE = os.path.join(SCRIPT_DIR, f"{UP_NAME}.html")

# 可选: banner和头像的base64文件（如果没有则使用默认渐变色）
BANNER_B64_FILE = os.path.join(SCRIPT_DIR, "banner_b64.txt")
AVATAR_B64_FILE = os.path.join(SCRIPT_DIR, "avatar_b64.txt")
# ==========================================

# 加载banner和头像
banner_b64 = ""
avatar_b64 = ""
if os.path.exists(BANNER_B64_FILE):
    with open(BANNER_B64_FILE, 'r') as f:
        banner_b64 = f.read().strip()
if os.path.exists(AVATAR_B64_FILE):
    with open(AVATAR_B64_FILE, 'r') as f:
        avatar_b64 = f.read().strip()

# 加载数据
if not os.path.exists(CSV_FILE):
    print(f"错误: 找不到CSV文件 {CSV_FILE}")
    print(f"请先运行 bilibili_scraper.py 爬取数据")
    sys.exit(1)

videos = []
with open(CSV_FILE, 'r', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        videos.append(row)

cover_map = {}
if os.path.exists(COVER_CACHE):
    with open(COVER_CACHE, 'r') as f:
        cover_map = json.load(f)

print(f'视频: {len(videos)}, 封面: {len(cover_map)}')

# 构建JS数据（去重by bvid）
seen = set()
js_data = []
total_play = 0
for v in videos:
    bvid = v['bvid']
    if bvid in seen:
        continue
    seen.add(bvid)
    b64 = cover_map.get(bvid, '')
    play = v.get('play', '0')
    if isinstance(play, str):
        play = int(play) if play.isdigit() else 0
    else:
        play = int(play)
    total_play += play
    ts = v.get('pubdate_ts', '0')
    if isinstance(ts, str):
        ts = int(ts) if ts.isdigit() else 0
    dm = v.get('danmaku', '0')
    dm = int(dm) if str(dm).isdigit() else 0
    fav = v.get('favorites', '0')
    fav = int(fav) if str(fav).isdigit() else 0
    comment = v.get('comment', '0')
    comment = int(comment) if str(comment).isdigit() else 0
    js_data.append({
        'bv': bvid,
        't': v.get('title', ''),
        'p': play,
        'dm': dm,
        'cm': comment,
        'fav': fav,
        'ts': ts,
        'date': v.get('pubdate', ''),
        'dur': v.get('duration', ''),
        'img': b64,
    })

total_str = str(len(js_data))
data_json = json.dumps(js_data, ensure_ascii=False, separators=(',', ':'))

# 格式化总播放量
def fmt_num(n):
    if n >= 100000000:
        return f'{n/100000000:.1f}亿'
    if n >= 10000:
        return f'{n/10000:.1f}万'
    return str(n)

total_play_str = fmt_num(total_play)

# banner样式：有图片用图片，没有则用渐变色
if banner_b64:
    banner_style = f"background-image:url(data:image/jpeg;base64,{banner_b64});background-position:center top;background-size:cover"
else:
    banner_style = "background:linear-gradient(135deg,#00a1d6 0%,#6dd5fa 50%,#2980b9 100%)"

# 头像：有图片用图片，没有则用默认SVG
if avatar_b64:
    avatar_html = f'<img src="data:image/png;base64,{avatar_b64}" alt="{UP_NAME}">'
else:
    avatar_html = f'<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#00a1d6;color:#fff;font-size:28px;font-weight:700">{UP_NAME[0]}</div>'

# JS部分（避免f-string转义大括号）
js_code = '''
var DATA = __DATA_JSON__;
var currentSort = "time-desc";
var searchText = "";
var currentPage = 1;
var PAGE_SIZE = 30;
var toastTimer = null;
var cachedList = null;
var isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);

var playSvg = '<svg width="14" height="14" viewBox="0 0 16 16"><path fill="#fff" d="M4.5 2.5l9 5.5-9 5.5z"/></svg>';
var dmSvg = '<svg width="14" height="14" viewBox="0 0 16 16"><path fill="#fff" d="M2 3h12a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5l-3 2.5V4a1 1 0 0 1 1-1zm1.5 3v1h3V6h-3zm0 2.5v1h5v-1h-5zm5-2.5v1h3V6h-3z"/></svg>';

function formatNum(n) {
    if (n >= 100000000) return (n / 100000000).toFixed(1) + "\\u4ebf";
    if (n >= 10000) return (n / 10000).toFixed(1) + "\\u4e07";
    return n.toString();
}

function closeModal() {
    document.getElementById("modalOverlay").classList.remove("show");
}

function showModal(bv, copied) {
    document.getElementById("modalMsg").innerHTML = copied
        ? "\\u5df2\\u590d\\u5236\\uff1a"
        : "\\u957f\\u6309\\u4e0b\\u65b9BV\\u53f7\\u590d\\u5236\\uff1a";
    document.getElementById("modalBv").textContent = bv;
    document.getElementById("modalOverlay").classList.add("show");
    document.querySelector(".modal-hint").innerHTML = copied
        ? "\\u8bf7\\u6253\\u5f00B\\u7ad9\\u7c98\\u8d34BV\\u53f7\\u89c2\\u770b \\u00b7 \\ud83d\\udc46 \\u70b9\\u51fbBV\\u53f7\\u53ef\\u518d\\u6b21\\u590d\\u5236"
        : "\\u70b9\\u51fb\\u4e0a\\u65b9BV\\u53f7 \\u2192 \\u957f\\u6309\\u5168\\u9009 \\u2192 \\u590d\\u5236\\uff0c\\u7136\\u540e\\u6253\\u5f00B\\u7ad9\\u7c98\\u8d34\\u89c2\\u770b";
}

function tryClipboard(bv) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            navigator.clipboard.writeText(bv).then(function() {
                showModal(bv, true);
            }, function() {
                fallbackCopy(bv);
            });
            return;
        } catch(e) {}
    }
    fallbackCopy(bv);
}

function fallbackCopy(bv) {
    var ok = false;
    try {
        var ta = document.createElement("textarea");
        ta.value = bv;
        ta.style.cssText = "position:fixed;top:0;left:0;width:2em;height:2em;padding:0;border:none;outline:none;box-shadow:none;background:transparent;font-size:16px";
        document.body.appendChild(ta);
        ta.focus();
        ta.setSelectionRange(0, bv.length);
        ok = document.execCommand("copy");
        document.body.removeChild(ta);
    } catch(e) { ok = false; }
    showModal(bv, ok);
}

function doCopy(bv) {
    tryClipboard(bv);
}

function copyBV(bv) {
    doCopy(bv);
}

function cardClick(bv, e) {
    if (isMobile) {
        if (e) e.preventDefault();
        doCopy(bv);
    } else {
        window.open("https://www.bilibili.com/video/" + bv + "/", "_blank");
    }
}

function setSort(el) {
    document.querySelectorAll(".tab-item").forEach(function(b) { b.classList.remove("active"); });
    el.classList.add("active");
    currentSort = el.getAttribute("data-sort");
    currentPage = 1;
    cachedList = null;
    render();
}

function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function getFiltered() {
    if (cachedList) return cachedList;
    var list = DATA;
    if (searchText) {
        var q = searchText.toLowerCase();
        list = list.filter(function(v) {
            return v.t.toLowerCase().indexOf(q) !== -1 || v.bv.toLowerCase().indexOf(q) !== -1;
        });
    }
    list = list.slice();
    switch (currentSort) {
        case "time-desc": list.sort(function(a, b) { return b.ts - a.ts; }); break;
        case "time-asc": list.sort(function(a, b) { return a.ts - b.ts; }); break;
        case "play-desc": list.sort(function(a, b) { return b.p - a.p; }); break;
        case "fav-desc": list.sort(function(a, b) { return b.fav - a.fav; }); break;
    }
    cachedList = list;
    return list;
}

function goPage(p) {
    var list = getFiltered();
    var totalPages = Math.ceil(list.length / PAGE_SIZE);
    if (p < 1) p = 1;
    if (p > totalPages) p = totalPages;
    currentPage = p;
    renderGrid();
    renderPager();
    var nav = document.getElementById("spaceNav");
    if (nav) {
        var rect = nav.getBoundingClientRect();
        if (rect.top < 0 || rect.top > 200) {
            nav.scrollIntoView({behavior: "smooth"});
        }
    }
}

function renderPager() {
    var list = getFiltered();
    var totalPages = Math.ceil(list.length / PAGE_SIZE);
    var pager = document.getElementById("pager");
    if (totalPages <= 1) { pager.innerHTML = ""; return; }

    var html = "";
    html += '<button class="pager-btn' + (currentPage <= 1 ? " disabled" : "") + '" onclick="goPage(' + (currentPage - 1) + ')">&lt;</button>';

    var pages = [];
    pages.push(1);
    var start = Math.max(2, currentPage - 2);
    var end = Math.min(totalPages - 1, currentPage + 2);
    if (start > 2) pages.push(-1);
    for (var i = start; i <= end; i++) pages.push(i);
    if (end < totalPages - 1) pages.push(-1);
    if (totalPages > 1) pages.push(totalPages);

    for (var j = 0; j < pages.length; j++) {
        var pg = pages[j];
        if (pg === -1) {
            html += '<span class="pager-ellipsis">...</span>';
        } else {
            html += '<button class="pager-btn' + (pg === currentPage ? " active" : "") + '" onclick="goPage(' + pg + ')">' + pg + '</button>';
        }
    }

    html += '<button class="pager-btn' + (currentPage >= totalPages ? " disabled" : "") + '" onclick="goPage(' + (currentPage + 1) + ')">&gt;</button>';
    html += '<span class="pager-jump">\\u8df3\\u81f3<input type="number" id="jumpInput" min="1" max="' + totalPages + '" value="' + currentPage + '" onkeydown="if(event.key===\\x27Enter\\x27)goPage(+this.value)">/' + totalPages + '\\u9875</span>';

    pager.innerHTML = html;
}

function renderGrid() {
    var list = getFiltered();
    var grid = document.getElementById("videoGrid");
    var noResult = document.getElementById("noResult");
    var totalPages = Math.ceil(list.length / PAGE_SIZE);

    document.getElementById("sectionCount").textContent = "\\u00b7 " + list.length;
    document.getElementById("countInfo").textContent = searchText
        ? ("\\u663e\\u793a " + list.length + " / " + DATA.length)
        : ("\\u7b2c " + currentPage + " / " + totalPages + " \\u9875");

    if (list.length === 0) {
        grid.innerHTML = "";
        noResult.style.display = "";
        return;
    }
    noResult.style.display = "none";

    var startIdx = (currentPage - 1) * PAGE_SIZE;
    var endIdx = Math.min(startIdx + PAGE_SIZE, list.length);
    var pageList = list.slice(startIdx, endIdx);

    var html = "";
    for (var i = 0; i < pageList.length; i++) {
        var v = pageList[i];
        var imgHtml = v.img
            ? '<img src="data:image/jpeg;base64,' + v.img + '" loading="lazy">'
            : '<div class="no-cover">\\u6682\\u65e0\\u5c01\\u9762</div>';

        html += '<div class="bili-video-card" onclick="cardClick(\\x27' + v.bv + '\\x27,event)">'
            + '<div class="card-cover">' + imgHtml
            + '<div class="cover-stats">'
            + '<span class="stat-item">' + playSvg + formatNum(v.p) + '</span>'
            + '<span class="stat-item">' + dmSvg + formatNum(v.dm) + '</span>'
            + '<span class="dur">' + v.dur + '</span>'
            + '</div></div>'
            + '<div class="card-info">'
            + '<div class="card-title">' + escHtml(v.t) + '</div>'
            + '<div class="card-meta">'
            + '<span>' + v.date.substring(0, 10) + '</span>'
            + '<span class="bvid" onclick="event.stopPropagation();doCopy(\\x27' + v.bv + '\\x27)">' + v.bv + '</span>'
            + '</div></div></div>';
    }
    grid.innerHTML = html;
}

function render() {
    cachedList = null;
    renderGrid();
    renderPager();
}

var searchTimer = null;
document.getElementById("searchInput").addEventListener("input", function() {
    var val = this.value.trim();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function() {
        searchText = val;
        currentPage = 1;
        cachedList = null;
        render();
    }, 300);
});

window.addEventListener("scroll", function() {
    var btn = document.getElementById("backTop");
    if (window.scrollY > 400) btn.classList.add("show");
    else btn.classList.remove("show");
});

render();
'''.replace('__DATA_JSON__', data_json)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{UP_NAME} 的个人空间 - 视频存档</title>
<style>
/* Reset & Base */
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:#f1f2f3;color:#18191c;font-size:14px;-webkit-text-size-adjust:100%}}
a{{text-decoration:none;color:inherit}}

/* B站顶部导航栏 */
.bili-header{{height:64px;background:#fff;display:flex;align-items:center;padding:0 24px;box-shadow:0 1px 2px rgba(0,0,0,.05);position:sticky;top:0;z-index:200}}
.bili-header .logo{{height:36px;margin-right:20px}}
.bili-header .logo svg{{height:36px;width:auto}}

/* 空间头图区域 */
.space-banner{{position:relative;height:320px;{banner_style};display:block}}
@media(max-width:768px){{.space-banner{{height:220px}}}}

/* 用户信息 - 磨砂透明浮在banner底部 */
.space-userinfo-bg{{position:relative;margin-top:-90px;z-index:10}}
.space-userinfo-glass{{background:rgba(255,255,255,.65);-webkit-backdrop-filter:blur(20px) saturate(180%);backdrop-filter:blur(20px) saturate(180%);border-top:1px solid rgba(255,255,255,.5)}}
.space-userinfo{{max-width:1200px;margin:0 auto;padding:14px 20px}}
.userinfo-inner{{display:flex;align-items:center}}
.user-avatar{{width:72px;height:72px;border-radius:50%;border:3px solid #fff;background:#e3e5e7;overflow:hidden;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
.user-avatar img{{width:100%;height:100%;object-fit:cover}}
.user-detail{{margin-left:16px}}
.user-name{{font-size:20px;font-weight:700;color:#18191c;display:flex;align-items:center;gap:8px}}
.user-stats{{display:flex;gap:20px;margin-top:6px;font-size:13px;color:#61666d}}
.user-stats .stat-item{{cursor:default}}
.user-stats .stat-num{{color:#18191c;font-weight:600;margin-right:2px}}
.user-btns{{margin-left:auto;display:flex;gap:10px}}
.btn-uid{{background:rgba(255,255,255,.7);color:#61666d;border:1px solid rgba(255,255,255,.8);padding:7px 16px;border-radius:8px;font-size:14px;cursor:default;-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}}
@media(max-width:768px){{
    .space-userinfo-bg{{margin-top:-70px}}
    .userinfo-inner{{flex-wrap:wrap}}
    .user-avatar{{width:56px;height:56px}}
    .user-btns{{display:none}}
}}

/* 导航标签栏 */
.space-nav{{background:#fff;border-bottom:1px solid #e3e5e7;position:sticky;top:0;z-index:100;margin-top:-1px}}
.space-nav-inner{{max-width:1200px;margin:0 auto;display:flex;align-items:center;padding:0 20px}}
.nav-item{{padding:14px 20px;font-size:15px;color:#61666d;cursor:pointer;position:relative;white-space:nowrap}}
.nav-item:hover{{color:#18191c}}
.nav-item.active{{color:#18191c;font-weight:500}}
.nav-item.active::after{{content:'';position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:28px;height:3px;background:#00a1d6;border-radius:2px}}
.nav-search{{margin-left:auto;position:relative}}
.nav-search input{{width:200px;height:32px;border:1px solid #e3e5e7;border-radius:8px;padding:0 36px 0 12px;font-size:13px;outline:none;background:#f1f2f3;color:#18191c;transition:border-color .2s,background .2s}}
.nav-search input:focus{{border-color:#00a1d6;background:#fff}}
.nav-search .search-icon{{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:#9499a0;pointer-events:none}}
@media(max-width:768px){{
    .nav-item{{padding:12px 12px;font-size:14px}}
    .nav-search input{{width:120px}}
}}

/* 主内容区 */
.space-main{{max-width:1200px;margin:20px auto;padding:0 20px}}

/* 视频区标题栏 */
.section-header{{display:flex;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px}}
.section-title{{font-size:18px;font-weight:600;color:#18191c}}
.section-count{{font-size:14px;color:#9499a0;margin-left:4px}}
.section-tabs{{display:flex;gap:0;margin-left:24px;background:#f1f2f3;border-radius:8px;overflow:hidden}}
.tab-item{{padding:6px 16px;font-size:13px;color:#61666d;cursor:pointer;transition:all .2s;border:none;background:transparent;font-family:inherit}}
.tab-item:hover{{color:#18191c}}
.tab-item.active{{background:#fff;color:#18191c;font-weight:500;box-shadow:0 1px 2px rgba(0,0,0,.05);border-radius:8px}}
.section-right{{margin-left:auto;display:flex;align-items:center;gap:12px}}
.count-info{{font-size:13px;color:#9499a0}}
@media(max-width:768px){{
    .section-tabs{{margin-left:0}}
    .section-right{{display:none}}
}}

/* 视频卡片网格 */
.video-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}
@media(max-width:768px){{.video-grid{{grid-template-columns:repeat(2,1fr);gap:8px}}}}
@media(min-width:1200px){{.video-grid{{grid-template-columns:repeat(5,1fr)}}}}

/* 单个视频卡片 */
.bili-video-card{{background:#fff;border-radius:8px;overflow:hidden;transition:box-shadow .2s,transform .2s;cursor:pointer}}
.bili-video-card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.1);transform:translateY(-2px)}}
.bili-video-card .card-cover{{position:relative;width:100%;padding-top:56.25%;background:#e3e5e7;overflow:hidden}}
.bili-video-card .card-cover img{{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}}
.bili-video-card .card-cover .no-cover{{position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#c9ccd0;font-size:12px;background:#e3e5e7}}
.bili-video-card .cover-stats{{position:absolute;bottom:0;left:0;right:0;display:flex;align-items:center;padding:4px 8px;background:linear-gradient(transparent,rgba(0,0,0,.7));color:#fff;font-size:11px;gap:12px}}
.cover-stats .stat-item{{display:flex;align-items:center;gap:3px}}
.cover-stats .stat-item svg{{width:14px;height:14px;fill:#fff;opacity:.9}}
.cover-stats .dur{{margin-left:auto;background:rgba(0,0,0,.5);padding:1px 6px;border-radius:4px;font-size:11px}}
.bili-video-card .card-info{{padding:8px 10px 10px}}
.bili-video-card .card-title{{font-size:13px;line-height:1.5;color:#18191c;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-all;height:39px}}
.bili-video-card:hover .card-title{{color:#00a1d6}}
.bili-video-card .card-meta{{display:flex;align-items:center;justify-content:space-between;margin-top:6px;font-size:12px;color:#9499a0}}
.bili-video-card .card-meta .bvid{{font-family:"SF Mono",Monaco,Menlo,monospace;color:#00a1d6;font-size:11px}}

/* 磨砂弹窗（手机端复制BV号） */
.modal-overlay{{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.35);z-index:9998;display:none;align-items:center;justify-content:center;-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}}
.modal-overlay.show{{display:flex}}
.modal-box{{background:rgba(255,255,255,.85);-webkit-backdrop-filter:blur(24px) saturate(180%);backdrop-filter:blur(24px) saturate(180%);border-radius:16px;padding:28px 24px 24px;max-width:380px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.15);position:relative;text-align:center;border:1px solid rgba(255,255,255,.6)}}
.modal-box .modal-close{{position:absolute;top:10px;right:14px;width:28px;height:28px;border:none;background:rgba(0,0,0,.06);border-radius:50%;cursor:pointer;font-size:16px;color:#61666d;display:flex;align-items:center;justify-content:center;transition:background .2s}}
.modal-box .modal-close:hover{{background:rgba(0,0,0,.12)}}
.modal-box .modal-icon{{font-size:36px;margin-bottom:12px}}
.modal-box .modal-msg{{font-size:15px;color:#18191c;line-height:1.6;word-break:break-all}}
.modal-box .modal-bv{{display:inline-block;margin-top:8px;padding:6px 16px;background:rgba(0,161,214,.1);color:#00a1d6;border-radius:8px;font-family:"SF Mono",Monaco,Menlo,monospace;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s;user-select:all}}
.modal-box .modal-bv:hover{{background:rgba(0,161,214,.2)}}
.modal-box .modal-hint{{font-size:12px;color:#9499a0;margin-top:12px}}

/* 页脚 */
.space-footer{{text-align:center;padding:40px 20px;color:#9499a0;font-size:13px;border-top:1px solid #e3e5e7;margin-top:40px;background:#fff}}

/* 回到顶部 */
.back-top{{position:fixed;bottom:60px;right:24px;width:40px;height:40px;background:#fff;border:1px solid #e3e5e7;border-radius:8px;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.08);z-index:100;opacity:0;transition:opacity .3s;color:#61666d}}
.back-top.show{{opacity:1}}
.back-top:hover{{border-color:#00a1d6;color:#00a1d6}}

/* 无结果 */
.no-result{{text-align:center;padding:80px 20px;color:#9499a0;font-size:15px}}

/* 分页器 */
.pager{{display:flex;align-items:center;justify-content:center;gap:6px;padding:24px 0;flex-wrap:wrap}}
.pager-btn{{min-width:36px;height:36px;border:1px solid #e3e5e7;border-radius:8px;background:#fff;color:#18191c;font-size:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;padding:0 8px}}
.pager-btn:hover{{border-color:#00a1d6;color:#00a1d6}}
.pager-btn.active{{background:#00a1d6;color:#fff;border-color:#00a1d6;font-weight:500}}
.pager-btn.disabled{{color:#c9ccd0;cursor:default;pointer-events:none}}
.pager-ellipsis{{color:#9499a0;font-size:14px;padding:0 4px;user-select:none}}
.pager-jump{{font-size:13px;color:#9499a0;display:flex;align-items:center;gap:4px;margin-left:8px}}
.pager-jump input{{width:48px;height:32px;border:1px solid #e3e5e7;border-radius:6px;text-align:center;font-size:13px;outline:none;color:#18191c}}
.pager-jump input:focus{{border-color:#00a1d6}}
</style>
</head>
<body>

<!-- B站顶部导航 -->
<div class="bili-header">
  <div class="logo">
    <svg viewBox="0 0 512 512" height="36"><path fill="#00a1d6" d="M306.73 60.72l43.08-42.28a12 12 0 0 1 16.87 0 11.81 11.81 0 0 1 0 16.71l-30.57 30h31.68c35.15 0 63.68 28.27 63.68 63.1v219.58c0 34.83-28.53 63.1-63.68 63.1H144.21c-35.15 0-63.68-28.27-63.68-63.1V128.27c0-34.83 28.53-63.1 63.68-63.1h31.68l-30.57-30a11.81 11.81 0 0 1 0-16.71 12 12 0 0 1 16.87 0l43.08 42.28h101.46zM367.79 88.86H144.21c-21.94 0-39.73 17.6-39.73 39.41v219.58c0 21.8 17.8 39.41 39.73 39.41h223.58c21.94 0 39.73-17.6 39.73-39.41V128.27c0-21.8-17.8-39.41-39.73-39.41zM196.58 218.69c13.22 0 23.95 10.69 23.95 23.82a23.87 23.87 0 0 1-23.95 23.82c-13.22 0-23.95-10.7-23.95-23.82s10.73-23.82 23.95-23.82zm118.84 0c13.22 0 23.95 10.69 23.95 23.82a23.87 23.87 0 0 1-23.95 23.82c-13.22 0-23.95-10.7-23.95-23.82s10.73-23.82 23.95-23.82z"/></svg>
  </div>
  <span style="font-size:15px;color:#18191c;font-weight:500">{UP_NAME} - 视频存档</span>
</div>

<!-- 空间头图 -->
<div class="space-banner"></div>

<!-- 用户信息 -->
<div class="space-userinfo-bg">
<div class="space-userinfo-glass">
<div class="space-userinfo">
  <div class="userinfo-inner">
    <div class="user-avatar">
      {avatar_html}
    </div>
    <div class="user-detail">
      <div class="user-name">{UP_NAME}</div>
      <div class="user-stats">
        <span class="stat-item"><span class="stat-num">{total_play_str}</span>播放</span>
        <span class="stat-item"><span class="stat-num">{total_str}</span>视频</span>
      </div>
    </div>
    <div class="user-btns">
      <button class="btn-uid">UID: {UP_UID}</button>
    </div>
  </div>
</div>
</div>
</div>

<!-- 导航栏 -->
<div class="space-nav" id="spaceNav">
  <div class="space-nav-inner">
    <div class="nav-item active">投稿</div>
    <div class="nav-search">
      <input type="text" id="searchInput" placeholder="搜索视频">
      <span class="search-icon">
        <svg width="16" height="16" viewBox="0 0 16 16"><path fill="#9499a0" d="M6.5 1a5.5 5.5 0 0 1 4.383 8.823l3.896 3.9a.75.75 0 0 1-1.06 1.06l-3.9-3.896A5.5 5.5 0 1 1 6.5 1zm0 1.5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/></svg>
      </span>
    </div>
  </div>
</div>

<!-- 主内容 -->
<div class="space-main">
  <div class="section-header">
    <span class="section-title">视频</span>
    <span class="section-count" id="sectionCount">&middot; {total_str}</span>
    <div class="section-tabs">
      <button class="tab-item active" data-sort="time-desc" onclick="setSort(this)">最新发布</button>
      <button class="tab-item" data-sort="play-desc" onclick="setSort(this)">最多播放</button>
      <button class="tab-item" data-sort="fav-desc" onclick="setSort(this)">最多收藏</button>
    </div>
    <div class="section-right">
      <span class="count-info" id="countInfo"></span>
    </div>
  </div>

  <div class="video-grid" id="videoGrid"></div>
  <div class="no-result" id="noResult" style="display:none">没有找到相关视频</div>
  <div class="pager" id="pager"></div>
</div>

<!-- 页脚 -->
<div class="space-footer">
  {UP_NAME} 视频存档 &middot; 共 {total_str} 个视频 &middot; UID: {UP_UID}<br>
  <span style="color:#c9ccd0;font-size:12px;margin-top:8px;display:inline-block">本页面为离线存档，数据截至爬取时间</span>
</div>

<!-- 磨砂弹窗 -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <div class="modal-icon">&#9989;</div>
    <div class="modal-msg" id="modalMsg"></div>
    <div class="modal-bv" id="modalBv" onclick="copyBV(this.textContent)"></div>
    <div class="modal-hint"></div>
  </div>
</div>

<!-- 回到顶部 -->
<div class="back-top" id="backTop" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">
  <svg width="16" height="16" viewBox="0 0 16 16"><path fill="currentColor" d="M8 3.5l5.5 5.5h-3.75v3.5h-3.5V9H2.5z"/></svg>
</div>

<script>
''' + js_code + '''
</script>
</body>
</html>'''

with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html)

size_mb = os.path.getsize(HTML_FILE) / 1024 / 1024
print(f'\nHTML生成完成!')
print(f'  文件: {HTML_FILE}')
print(f'  大小: {size_mb:.1f} MB')
print(f'  视频数: {len(js_data)}')
print(f'  有封面: {sum(1 for d in js_data if d["img"])}')
