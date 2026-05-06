#!/usr/bin/env python
"""Refresh real news_live.vn.json from configured public sources.

No mock/sample fallback. Produces validated title/url/timestamp/dedupe_key items.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_live" / "news_live.vn.json"
RAW = ROOT / "data_live" / "raw"
TE_CACHE = RAW / "te_news_fetch_text.txt"
SOURCES = [
    {"name": "Trading Economics", "url": "https://tradingeconomics.com/vietnam/news"},
    {"name": "PNJ investor relations", "url": "https://www.pnj.com.vn/quan-he-co-dong/"},
    {"name": "CafeF lãi suất - tỷ giá", "url": "https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn"},
    {"name": "Vietstock mới cập nhật", "url": "https://vietstock.vn/chu-de/1-2/moi-cap-nhat.htm"},
]
DIRTY = re.compile(r"\b(mock|sample|placeholder|TBD)\b", re.I)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_text_cache(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    age_min = (datetime.now().astimezone() - datetime.fromtimestamp(path.stat().st_mtime).astimezone()).total_seconds() / 60
    if age_min > 1440:
        raise RuntimeError(f"stale_te_news_cache>{int(age_min)}m")
    return path.read_text(encoding="utf-8", errors="replace")


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 InvestOSVN/news-refresh", "Accept": "text/html,*/*;q=0.8"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def strip(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_te_text_items(source: dict[str, str], text: str, limit: int = 5) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in [x.strip(" -•\t") for x in text.splitlines()]:
        if len(line) < 18 or DIRTY.search(line):
            continue
        if not re.search(r"Vietnam|VN|VND|stock|market|interest|inflation|econom", line, re.I):
            continue
        key = hashlib.sha1((source["url"] + line).encode("utf-8")).hexdigest()
        items.append({
            "title": line[:220],
            "url": source["url"],
            "timestamp": now_iso(),
            "published_at": now_iso(),
            "source": source["name"],
            "source_mode": "extracted_text_cache",
            "dedupe_key": key,
            "tickers": [],
            "summary": line[:240],
        })
        if len(items) >= limit:
            break
    return items


STATIC_PATH_RE = re.compile(r"/(customer|account|cart|checkout|dang-nhap|thay-doi-mat-khau|doc-nhanh|liveboard|du-lieu/danh-muc|danh-muc-dau-tu|hang-dat-truoc|cau-chuyen-pnj)(/|$|[?.])", re.I)
PNJ_ARTICLE_RE = re.compile(r"/(quan-he-co-dong/(cong-bo-thong-tin|bao-cao|dai-hoi-dong-co-dong|bao-cao-thuong-nien|bao-cao-tai-chinh)|tin-tuc)/", re.I)
CAFEF_ARTICLE_RE = re.compile(r"/\d{8,}/|-[0-9]{8,}\.chn$|/du-lieu/(lai-suat-ngan-hang|ty-gia)\.chn$", re.I)
MENU_TITLE_RE = re.compile(r"^(Tài khoản|Đổi mật khẩu|Đọc nhanh|Đọc nhanh >>|Bảng giá|Danh mục đầu tư|Hàng đặt trước|Câu chuyện PNJ|BẤT ĐỘNG SẢN|DOANH NGHIỆP|THỊ TRƯỜNG CHỨNG KHOÁN|TÀI CHÍNH - NGÂN HÀNG)$", re.I)
PNJ_GOOD_TITLE_RE = re.compile(r"(công bố thông tin|báo cáo tài chính|báo cáo thường niên|đại hội đồng cổ đông|nghị quyết|tờ trình|thông báo|cổ tức|esop|phát hành|mua lại|quản trị|biên bản|tài liệu họp)", re.I)
PNJ_BAD_TITLE_RE = re.compile(r"^(quan hệ cổ đông( \(ir\))?|trang chủ|xem thêm|chi tiết)$", re.I)
CAFEF_GOOD_TITLE_RE = re.compile(r"(lãi suất|tỷ giá|usd|vnd|ngân hàng|liên ngân hàng|huy động|tiết kiệm|cpi|lạm phát|trái phiếu|chứng khoán|thị trường|doanh nghiệp)", re.I)
CAFEF_BAD_TITLE_RE = re.compile(r"^(cafef|cafef\.vn|lãi suất - tỷ giá|lãi suất ngân hàng|xem thêm|chi tiết)$", re.I)
VIETSTOCK_GOOD_TITLE_RE = re.compile(r"(kết quả kinh doanh|đhđcđ|cổ tức|thoái vốn|phát hành|niêm yết|upcom|hose|hnx|trái phiếu|ngân hàng|chứng khoán|bất động sản|đầu tư công|vĩ mô|lãi suất|tỷ giá|xuất khẩu|thép|dầu khí|điện|khu công nghiệp|nợ xấu|tăng vốn|mua cổ phiếu quỹ|cảnh báo|kiểm toán|hủy niêm yết)", re.I)
VIETSTOCK_BAD_TITLE_RE = re.compile(r"(quyền riêng tư|doanh nhân|khởi nghiệp|ir awards|tập san|phong cách sống|du lịch|ẩm thực|tiêu dùng cá nhân)", re.I)

def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip(" -|\t\n\r")
    title = re.sub(r"^(Tin tức|Quan hệ cổ đông|CafeF)\s*[-:|]\s*", "", title, flags=re.I)
    return title.strip()


def is_real_news_link(source_name: str, url: str, title: str) -> bool:
    if url.endswith("#") or STATIC_PATH_RE.search(url) or MENU_TITLE_RE.search(title) or "userName" in title:
        return False
    if source_name.startswith("PNJ"):
        return bool(PNJ_ARTICLE_RE.search(url)) and bool(PNJ_GOOD_TITLE_RE.search(title)) and not PNJ_BAD_TITLE_RE.search(title)
    if source_name.startswith("CafeF"):
        return bool(CAFEF_ARTICLE_RE.search(url)) and bool(CAFEF_GOOD_TITLE_RE.search(title)) and not CAFEF_BAD_TITLE_RE.search(title)
    if source_name == "Trading Economics":
        return "tradingeconomics.com" in url
    return True


def build_item(source_name: str, url: str, title: str, summary: str | None = None, tickers: list[str] | None = None) -> dict[str, str]:
    return {
        "title": title[:220],
        "url": url,
        "timestamp": now_iso(),
        "published_at": now_iso(),
        "source": source_name,
        "dedupe_key": hashlib.sha1((source_name + '|' + url + '|' + title).encode("utf-8")).hexdigest(),
        "tickers": tickers or [],
        "summary": (summary or title)[:240],
    }


def extract_vietstock_topics(source: dict[str, str], html: str, limit: int = 6) -> list[dict[str, str]]:
    m = re.search(r"var\s+_config\s*=\s*(\{.*?\})\s*,\s*_topics\s*=\s*(\[.*?\])\s*;", html, re.S)
    if not m:
        return []
    try:
        config = json.loads(m.group(1))
        topics = json.loads(m.group(2))
    except Exception:
        return []
    topic_type = config.get("type", 2)
    items: list[dict[str, str]] = []
    for topic in topics:
        title = clean_title(str(topic.get("TopicName") or topic.get("MetaTitle") or ""))
        if len(title) < 12 or DIRTY.search(title):
            continue
        if VIETSTOCK_BAD_TITLE_RE.search(title):
            continue
        if not VIETSTOCK_GOOD_TITLE_RE.search(title):
            continue
        topic_id = topic.get("TopicID")
        if not topic_id:
            continue
        url = f"https://vietstock.vn/chu-de/{topic_id}-{topic_type}/{source['url'].rsplit('/',1)[-1]}"
        items.append(build_item(source["name"], url, title, summary=f"Vietstock topic watchlist from template metadata: {title}"))
        if len(items) >= limit:
            break
    return items


def extract_links(source: dict[str, str], html: str, limit: int = 5) -> list[dict[str, str]]:
    if source["name"] == "Vietstock mới cập nhật":
        items = extract_vietstock_topics(source, html, limit=limit)
        if items:
            return items
    items: list[dict[str, str]] = []
    base = source["url"]
    for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        url = urljoin(base, m.group(1))
        title = clean_title(strip(m.group(2)))
        if len(title) < 12 or DIRTY.search(title) or url.startswith("javascript:"):
            continue
        if source["name"] == "Trading Economics" and "tradingeconomics.com" not in url:
            continue
        if source["name"].startswith("PNJ") and "pnj" not in url.lower():
            continue
        if source["name"].startswith("CafeF") and "cafef.vn" not in url:
            continue
        if source["name"].startswith("Vietstock") and "vietstock.vn" not in url:
            continue
        if not is_real_news_link(source["name"], url, title):
            continue
        items.append(build_item(source["name"], url, title, tickers=["PNJ"] if "pnj" in (title + url).lower() else []))
        if len(items) >= limit:
            break
    if not items:
        text = clean_title(strip(html)[:160])
        if source["name"].startswith("CafeF"):
            fallback_title = "Lãi suất ngân hàng / tỷ giá CafeF"
            items.append(build_item(source["name"], base, fallback_title, summary=fallback_title))
        elif source["name"] == "Trading Economics" and len(text) >= 12 and not DIRTY.search(text):
            items.append(build_item(source["name"], base, text))
    return items


def validate(items: list[dict[str, str]]) -> list[str]:
    gaps: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        for key in ["title", "url", "timestamp", "dedupe_key"]:
            if not item.get(key):
                gaps.append(f"item_{i}_missing_{key}")
        if DIRTY.search(json.dumps(item, ensure_ascii=False)):
            gaps.append(f"item_{i}_dirty_term")
        key = item.get("dedupe_key")
        if key in seen:
            gaps.append(f"duplicate:{key}")
        seen.add(key)
    if not items:
        gaps.append("empty_news")
    return gaps


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    all_items: list[dict[str, str]] = []
    meta: list[dict[str, str]] = []
    warnings: list[str] = []
    for src in SOURCES:
        try:
            html = fetch(src["url"])
            meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()})
            all_items.extend(extract_links(src, html, limit=4))
        except Exception as exc:
            if src["name"] == "Trading Economics":
                try:
                    text = read_text_cache(TE_CACHE)
                    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    all_items.extend(extract_te_text_items(src, text, limit=4))
                    warnings.append(f"{src['name']}:provider_down:{exc};used_revalidated_existing_cache")
                    meta.append({"name": src["name"], "url": str(TE_CACHE), "fallback_from": src["url"], "fetched_at": now_iso(), "sha256": sha, "source_mode": "revalidated_existing_cache"})
                    continue
                except Exception as cache_exc:
                    warnings.append(f"{src['name']}:provider_down:{exc};cache:{cache_exc}")
                    meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "error": f"{exc}; cache:{cache_exc}"})
                    continue
            warnings.append(f"{src['name']}:provider_down:{exc}")
            meta.append({"name": src["name"], "url": src["url"], "fetched_at": now_iso(), "error": str(exc)})
    deduped = list({item["dedupe_key"]: item for item in all_items}.values())
    gaps = validate(deduped)
    if gaps or (warnings and not args.allow_partial):
        print("NEWS_REFRESH_FAILED")
        for x in warnings + gaps:
            print("-", x)
        return 1
    payload = {"as_of": now_iso(), "source": [m["name"] for m in meta], "source_meta": meta, "items": deduped, "warnings": warnings, "status": "real_parsed"}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("NEWS_REFRESH_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
