"""
B站UP主视频信息爬取工具
- 使用curl_cffi模拟Chrome TLS指纹，绕过412风控
- 多排序策略绕过100页限制（pubdate + click + stow）
- 去重合并，下载封面，生成自包含HTML

用法:
    1. 修改下方 TARGET_MID 为目标UP主的UID
    2. pip install curl_cffi Pillow
    3. python bilibili_scraper.py
"""

import hashlib
import urllib.parse
import time
import json
import csv
import random
import os
import sys
import base64
import io
from datetime import datetime

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("请先安装 curl_cffi: pip install curl_cffi")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("请先安装 Pillow: pip install Pillow")
    sys.exit(1)

# ============ 配置（修改此处） ============
TARGET_MID = 0  # ← 替换为目标UP主的UID
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(OUTPUT_DIR, f"videos_{TARGET_MID}.csv")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")
COVER_CACHE_FILE = os.path.join(OUTPUT_DIR, "cover_cache.json")
PAGE_SIZE = 30
MAX_PAGE = 100  # B站硬限制，超过100页返回412
REQUEST_DELAY = (2.0, 3.5)
IMAGE_MAX_KB = 2.5

# WBI签名置换表（从B站前端逆向提取，固定不变）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

CSV_FIELDS = [
    "bvid", "title", "play", "danmaku", "comment", "favorites",
    "coin", "like", "share", "pubdate", "pubdate_ts", "duration",
    "description", "cover_url", "link"
]

# ============ 核心函数 ============


def get_mixin_key(orig: str) -> str:
    """通过置换表重排密钥字符串，取前32位"""
    return "".join([orig[i] for i in MIXIN_KEY_ENC_TAB])[:32]


def new_session_and_keys():
    """创建新的curl_cffi会话并获取WBI密钥"""
    session = cffi_requests.Session(impersonate="chrome131")
    resp = session.get("https://api.bilibili.com/x/web-interface/nav")
    data = resp.json()["data"]["wbi_img"]
    img_key = data["img_url"].rsplit("/", 1)[1].split(".")[0]
    sub_key = data["sub_url"].rsplit("/", 1)[1].split(".")[0]
    mixin_key = get_mixin_key(img_key + sub_key)
    return session, mixin_key


def sign_params(params: dict, mixin_key: str) -> dict:
    """WBI签名：参数排序 + URL编码 + 拼接密钥 → MD5"""
    params["wts"] = str(int(time.time()))
    params_sorted = dict(sorted(params.items()))
    query = urllib.parse.urlencode(params_sorted)
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    params_sorted["w_rid"] = w_rid
    return dict(sorted(params_sorted.items()))


def format_duration(seconds) -> str:
    if isinstance(seconds, str):
        return seconds
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "N/A"
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fetch_page(session, mixin_key: str, page: int, order: str = "pubdate", tid: int = 0):
    """
    获取一页视频列表
    返回: (视频列表, 总数) 或失败时 raise Exception
    """
    params = {
        "mid": str(TARGET_MID),
        "ps": str(PAGE_SIZE),
        "tid": str(tid),
        "pn": str(page),
        "order": order,
    }
    signed = sign_params(params, mixin_key)
    url = "https://api.bilibili.com/x/space/wbi/arc/search?" + urllib.parse.urlencode(signed)
    resp = session.get(url)

    if resp.status_code == 412:
        raise Exception("412风控拦截")
    try:
        data = resp.json()
    except Exception:
        raise Exception(f"响应解析失败: status={resp.status_code}")

    if data["code"] != 0:
        raise Exception(f"API错误: code={data['code']}, message={data['message']}")

    vlist = data["data"]["list"]["vlist"]
    total = data["data"]["page"]["count"]

    videos = []
    for v in vlist:
        ts = v.get("created", 0)
        videos.append({
            "bvid": v.get("bvid", ""),
            "title": v.get("title", ""),
            "play": v.get("play", 0),
            "danmaku": v.get("video_review", 0),
            "comment": v.get("comment", 0),
            "favorites": v.get("favorites", 0),
            "coin": v.get("coin", 0) if "coin" in v else "",
            "like": v.get("like", 0) if "like" in v else "",
            "share": v.get("share", 0) if "share" in v else "",
            "pubdate": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
            "pubdate_ts": ts,
            "duration": format_duration(v.get("length", "")),
            "description": v.get("description", ""),
            "cover_url": v.get("pic", ""),
            "link": f"https://www.bilibili.com/video/{v.get('bvid', '')}/",
        })

    return videos, total


def fetch_all_with_order(order: str, existing_bvids: set, progress: dict):
    """用指定排序方式爬取所有可获取的视频（最多100页）"""
    progress_key = f"last_page_{order}"
    start_page = progress.get(progress_key, 0) + 1

    session, mixin_key = new_session_and_keys()
    new_videos = []
    consecutive_fails = 0

    # 获取总数（带重试）
    if start_page == 1:
        total_pages = None
        for init_try in range(8):
            try:
                _, total = fetch_page(session, mixin_key, 1, order)
                total_pages = min((total + PAGE_SIZE - 1) // PAGE_SIZE, MAX_PAGE)
                print(f"  [{order}] 总数: {total}，可获取前 {total_pages} 页")
                break
            except Exception as e:
                wait = (init_try + 1) * 3 + random.uniform(0, 3)
                print(f"  [{order}] 获取总数失败({init_try+1}/8): {e}，等{wait:.0f}s")
                time.sleep(wait)
                try:
                    session, mixin_key = new_session_and_keys()
                except Exception:
                    pass
        if total_pages is None:
            print(f"  [{order}] 无法获取总数，跳过")
            return []
    else:
        total_pages = MAX_PAGE
        print(f"  [{order}] 从第 {start_page} 页继续...")

    page = start_page
    key_refresh_counter = 0

    while page <= total_pages:
        try:
            key_refresh_counter += 1
            if key_refresh_counter >= 15:
                session, mixin_key = new_session_and_keys()
                key_refresh_counter = 0
                time.sleep(1)

            videos, total = fetch_page(session, mixin_key, page, order)
            total_pages = min((total + PAGE_SIZE - 1) // PAGE_SIZE, MAX_PAGE)

            # 只保留新视频
            new_count = 0
            for v in videos:
                if v["bvid"] not in existing_bvids:
                    new_videos.append(v)
                    existing_bvids.add(v["bvid"])
                    new_count += 1

            consecutive_fails = 0
            progress[progress_key] = page
            save_progress(progress)

            print(f"  [{order}] 第 {page}/{total_pages} 页 - 本轮新增 {len(new_videos)} (本页新 {new_count})")

            page += 1
            time.sleep(random.uniform(*REQUEST_DELAY))

        except Exception as e:
            consecutive_fails += 1
            if consecutive_fails > 8:
                print(f"  [{order}] 连续失败8次，停在第 {page} 页")
                break
            is_412 = "412" in str(e)
            if is_412:
                print(f"  [{order}] 第 {page} 页 412拦截，停止此排序方式")
                break
            wait = min(consecutive_fails * 5 + random.uniform(0, 5), 60)
            print(f"  [{order}] 第 {page} 页失败: {e}，等{wait:.0f}s ({consecutive_fails}/8)")
            time.sleep(wait)
            try:
                session, mixin_key = new_session_and_keys()
                key_refresh_counter = 0
            except Exception:
                pass

    return new_videos


def compress_image(img_data: bytes, max_kb: float = IMAGE_MAX_KB) -> str:
    """将图片压缩到指定大小以内，返回base64字符串"""
    try:
        img = Image.open(io.BytesIO(img_data))
        img = img.convert("RGB")
        max_bytes = int(max_kb * 1024)
        width = 160
        ratio = width / img.width
        height = int(img.height * ratio)
        img = img.resize((width, height), Image.LANCZOS)

        for quality in [60, 45, 30, 20, 15, 10, 5]:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                return base64.b64encode(buf.getvalue()).decode("ascii")

        img = img.resize((100, int(100 * height / width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=10, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def download_covers(all_videos: list) -> dict:
    """下载封面图片并压缩为base64，结果缓存到本地文件"""
    import requests as std_requests

    # 加载已有缓存
    cover_b64_map = {}
    if os.path.exists(COVER_CACHE_FILE):
        with open(COVER_CACHE_FILE, "r", encoding="utf-8") as f:
            cover_b64_map = json.load(f)
        print(f"  已加载 {len(cover_b64_map)} 张封面缓存")

    # 筛选需要下载的
    to_download = [v for v in all_videos if v["bvid"] not in cover_b64_map and v.get("cover_url")]
    print(f"  共 {len(to_download)} 张封面待下载...")

    session = std_requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for i, v in enumerate(to_download):
        bvid = v["bvid"]
        cover_url = v.get("cover_url", "")
        if cover_url:
            try:
                url = cover_url
                if url.startswith("//"):
                    url = "https:" + url
                elif url.startswith("http://"):
                    url = url.replace("http://", "https://", 1)
                thumb_url = url + "@320w_200h_1c.webp"
                resp = session.get(thumb_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    b64 = compress_image(resp.content)
                    if b64:
                        cover_b64_map[bvid] = b64
            except Exception:
                pass

        if (i + 1) % 200 == 0 or i == len(to_download) - 1:
            print(f"  封面: {i+1}/{len(to_download)} (成功 {len(cover_b64_map)})")
            # 每200张保存一次缓存
            with open(COVER_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cover_b64_map, f)

        if (i + 1) % 5 == 0:
            time.sleep(random.uniform(0.05, 0.15))

    # 最终保存
    with open(COVER_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cover_b64_map, f)

    return cover_b64_map


def write_csv(videos: list):
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for v in videos:
            writer.writerow({k: v.get(k, "") for k in CSV_FIELDS})


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)


def main():
    if TARGET_MID == 0:
        print("错误：请先修改 TARGET_MID 为目标UP主的UID")
        print("例如：TARGET_MID = 123456789")
        sys.exit(1)

    print("=== B站视频信息爬取工具 ===")
    print(f"目标UP主 UID: {TARGET_MID}")
    print(f"使用 curl_cffi (Chrome TLS指纹) + 多排序策略")
    print()

    progress = load_progress()
    all_videos_map = {}  # bvid -> video_dict，用于去重

    # 如果已有CSV，先加载
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                all_videos_map[row["bvid"]] = row
        print(f"  已加载 {len(all_videos_map)} 条历史记录")

    existing_bvids = set(all_videos_map.keys())

    # 阶段1: 多排序策略爬取
    print("\n[1/2] 多排序策略爬取视频列表...")
    sort_orders = ["pubdate", "click", "stow"]

    for order in sort_orders:
        print(f"\n  === 排序方式: {order} ===")
        new_videos = fetch_all_with_order(order, existing_bvids, progress)
        for v in new_videos:
            all_videos_map[v["bvid"]] = v
        save_progress(progress)
        write_csv(list(all_videos_map.values()))
        print(f"  [{order}] 完成，新增 {len(new_videos)} 条，总计 {len(all_videos_map)} 条")
        time.sleep(random.uniform(3, 5))  # 排序方式之间多等一会

    print(f"\n  去重后总计: {len(all_videos_map)} 条视频")
    all_videos = list(all_videos_map.values())

    # 阶段2: 下载封面
    print(f"\n[2/2] 下载封面图片...")
    cover_b64_map = download_covers(all_videos)
    print(f"  封面完成: {len(cover_b64_map)}/{len(all_videos)}")

    # 清理进度文件
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    print(f"\n=== 完成! ===")
    print(f"  视频数: {len(all_videos)}")
    print(f"  封面数: {len(cover_b64_map)}")
    print(f"  CSV: {CSV_FILE}")
    print(f"  封面缓存: {COVER_CACHE_FILE}")
    print(f"\n下一步: 运行 generate_html.py 生成可离线浏览的HTML网站")


if __name__ == "__main__":
    main()
