#!/usr/bin/env python
from __future__ import annotations
import argparse, io, json, math, re, time, zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data_live'
RAW = LIVE / 'raw' / 'cophieu68'
BASE = 'https://www.cophieu68.vn/'


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_text(v: Any) -> str:
    return re.sub(r'\s+', ' ', str(v or '').replace('\xa0', ' ')).strip()


def num(v: Any):
    s = clean_text(v)
    if not s or s in {'-', '—', 'N/A'}:
        return None
    s = s.replace('%', '').replace('x', '').replace('X', '').strip()
    mult = 1.0
    if s.lower().endswith('k'):
        mult = 1_000.0; s = s[:-1]
    elif s.lower().endswith('m'):
        mult = 1_000_000.0; s = s[:-1]
    elif s.lower().endswith('bi'):
        mult = 1_000_000_000.0; s = s[:-2]
    neg = s.startswith('(') and s.endswith(')')
    s = s.strip('()').replace(',', '')
    # Vietnamese pages sometimes use dot as decimal; keep decimal, remove thousands only when multiple dots.
    if s.count('.') > 1 and all(p.isdigit() for p in s.split('.')):
        s = ''.join(s.split('.'))
    try:
        x = float(s) * mult
        if neg:
            x = -x
        return int(x) if math.isfinite(x) and abs(x - int(x)) < 1e-9 else x
    except Exception:
        return None


def parse_date(v: str):
    s = clean_text(v)
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if not m:
        return None
    d, mo, y = m.groups()
    return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 invest-os-vn cophieu68-parser/0.1',
        'Accept-Language': 'vi,en;q=0.8',
    })
    return s


def fetch(s: requests.Session, url: str, raw_name: str | None = None) -> str:
    r = s.get(url, timeout=35)
    r.raise_for_status()
    r.encoding = 'utf-8'
    if raw_name:
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / raw_name).write_text(r.text, encoding='utf-8')
    return r.text


def table_rows(table):
    out = []
    for tr in table.find_all('tr'):
        cells = [clean_text(c.get_text(' ', strip=True)) for c in tr.find_all(['th', 'td'])]
        if any(cells):
            out.append(cells)
    return out


def parse_history_page(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    rows = []
    for t in tables:
        trs = table_rows(t)
        if not trs:
            continue
        header = trs[0]
        if 'Ngày' in header and 'Giá khớp' in header and 'Khối lượng' in header:
            for r in trs[1:]:
                if len(r) < 6:
                    continue
                dt = parse_date(r[0])
                if not dt:
                    continue
                rows.append({
                    'date': dt,
                    'close': num(r[1]),
                    'volume': num(r[2]),
                    'open': num(r[3]),
                    'high': num(r[4]),
                    'low': num(r[5]),
                    'foreign_buy': num(r[6]) if len(r) > 6 else None,
                    'foreign_sell': num(r[7]) if len(r) > 7 else None,
                    'foreign_value_bil_vnd': num(r[8]) if len(r) > 8 else None,
                    'raw': r,
                })
    max_page = 1
    for a in soup.find_all('a', href=True):
        m = re.search(r'[?&]cP=(\d+)', a['href'])
        if m:
            max_page = max(max_page, int(m.group(1)))
    return rows, max_page


def parse_history(s: requests.Session, ticker: str, max_pages: int):
    ticker_l = ticker.lower()
    all_rows = []
    discovered_max = 1
    for page in range(1, max_pages + 1):
        url = f'{BASE}quote/history.php?id={ticker_l}' if page == 1 else f'{BASE}quote/history.php?cP={page}&id={ticker_l}'
        html = fetch(s, url, f'{ticker_l}_history_p{page}.html')
        rows, maxp = parse_history_page(html)
        discovered_max = max(discovered_max, maxp)
        if not rows:
            break
        all_rows.extend(rows)
        time.sleep(0.25)
        if page >= discovered_max:
            break
    seen = set(); dedup = []
    for r in all_rows:
        if r['date'] in seen:
            continue
        seen.add(r['date']); dedup.append(r)
    return {
        'source_url': f'{BASE}quote/history.php?id={ticker_l}',
        'fetched_pages': min(max_pages, discovered_max),
        'discovered_pages': discovered_max,
        'row_count': len(dedup),
        'daily_ohlcv': dedup,
        'status': 'ok' if dedup else 'empty',
    }


def parse_summary(s: requests.Session, ticker: str):
    ticker_l = ticker.lower()
    url = f'{BASE}quote/summary.php?id={ticker_l}'
    html = fetch(s, url, f'{ticker_l}_summary.html')
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text('\n', strip=True)
    company = None
    m = re.search(r'CTCP[^\n]+|Ngân hàng[^\n]+|Tổng Công ty[^\n]+|Công ty[^\n]+', text)
    if m:
        company = clean_text(m.group(0))
    intraday = []
    for t in soup.find_all('table'):
        trs = table_rows(t)
        if trs and {'Thời gian', 'Giá khớp', 'Khối Lượng'}.issubset(set(trs[0])):
            for r in trs[1:]:
                if len(r) >= 5:
                    intraday.append({'time': r[0], 'matched_price': num(r[1]), 'change': num(r[2]), 'volume': num(r[3]), 'total_volume': num(r[4]), 'raw': r})
    return {'source_url': url, 'company_name_guess': company, 'intraday_trades': intraday, 'intraday_count': len(intraday), 'status': 'ok'}


def parse_financial_table(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup.find_all('table'):
        trs = table_rows(t)
        if trs and trs[0] and trs[0][0] == 'Chỉ tiêu' and len(trs[0]) > 2:
            periods = trs[0][1:]
            rows = []
            for r in trs[1:]:
                if len(r) < 2:
                    continue
                vals = {periods[i]: num(r[i + 1]) if i + 1 < len(r) else None for i in range(len(periods))}
                rows.append({'label': r[0], 'values_by_period': vals, 'raw': r})
            return periods, rows
    return [], []


def parse_financials(s: requests.Session, ticker: str):
    ticker_l = ticker.lower()
    out = {}
    for kind, url in {
        'summary': f'{BASE}quote/financial.php?id={ticker_l}',
        'detail_year': f'{BASE}quote/financial_detail.php?id={ticker_l}&type=year',
        'detail_quarter': f'{BASE}quote/financial_detail.php?id={ticker_l}&type=quarter',
    }.items():
        html = fetch(s, url, f'{ticker_l}_{kind}.html')
        periods, rows = parse_financial_table(html)
        out[kind] = {'source_url': url, 'periods': periods, 'rows': rows, 'row_count': len(rows), 'status': 'ok' if rows else 'empty'}
    return out


def parse_profile(s: requests.Session, ticker: str):
    ticker_l = ticker.lower()
    url = f'{BASE}quote/profile.php?id={ticker_l}'
    html = fetch(s, url, f'{ticker_l}_profile.html')
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for t in soup.find_all('table'):
        for r in table_rows(t):
            if len(r) >= 2 and len(r[0]) < 80:
                fields[r[0]] = r[1]
    return {'source_url': url, 'fields': fields, 'status': 'ok' if fields else 'empty'}


def parse_stockonline(s: requests.Session):
    url = f'{BASE}stockonline.php'
    html = fetch(s, url, 'stockonline.html')
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for t in soup.find_all('table'):
        trs = table_rows(t)
        if trs and trs[0] and 'MãCK' in trs[0][0]:
            for r in trs[2:]:
                if len(r) < 14:
                    continue
                rows.append({'ticker': r[0].upper(), 'raw': r})
            break
    return {'source_url': url, 'row_count': len(rows), 'rows': rows, 'status': 'ok' if rows else 'empty'}


def parse_amibroker_zip(s: requests.Session, kind: str):
    url = f'{BASE}download/_amibroker.php?type={kind}'
    r = s.get(url, timeout=60)
    r.raise_for_status()
    RAW.mkdir(parents=True, exist_ok=True)
    zip_path = RAW / f'amibroker_{kind}.zip'
    zip_path.write_bytes(r.content)
    rows = []
    members = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        members = zf.namelist()
        txt_name = next((n for n in members if n.lower().endswith('.txt')), members[0] if members else None)
        if txt_name:
            text = zf.read(txt_name).decode('utf-8', errors='replace')
            (RAW / f'amibroker_{kind}.txt').write_text(text, encoding='utf-8')
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('<'):
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 7:
                    continue
                d = parts[1]
                date = f'{d[:4]}-{d[4:6]}-{d[6:8]}' if re.match(r'^\d{8}$', d) else d
                rows.append({'ticker': parts[0].upper(), 'date': date, 'open': num(parts[2]), 'high': num(parts[3]), 'low': num(parts[4]), 'close': num(parts[5]), 'volume': num(parts[6]), 'raw': line})
    return {'source_url': url, 'content_type': r.headers.get('content-type'), 'zip_bytes': len(r.content), 'zip_members': members, 'row_count': len(rows), 'bars': rows, 'status': 'ok' if rows else 'empty'}


def parse_ticker(s: requests.Session, ticker: str, history_pages: int):
    ticker = ticker.upper()
    warnings = []
    rec = {'ticker': ticker, 'as_of': now_iso(), 'source': 'cophieu68.vn', 'status': 'ok'}
    for key, fn in [
        ('summary', lambda: parse_summary(s, ticker)),
        ('history', lambda: parse_history(s, ticker, history_pages)),
        ('financials', lambda: parse_financials(s, ticker)),
        ('profile', lambda: parse_profile(s, ticker)),
    ]:
        try:
            rec[key] = fn()
        except Exception as e:
            warnings.append(f'{ticker}:{key}:{type(e).__name__}:{e}')
            rec[key] = {'status': 'error', 'error': str(e)}
            rec['status'] = 'partial'
    rec['warnings'] = warnings
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tickers', default='FPT,VCB,HPG,SSI,MWG')
    ap.add_argument('--history-pages', type=int, default=3, help='polite cap; each page ~50 trading days')
    ap.add_argument('--include-stockonline', action='store_true')
    ap.add_argument('--download-amibroker', choices=['none', 'last', 'all'], default='none')
    ap.add_argument('--summary', action='store_true')
    args = ap.parse_args()
    tickers = [x.strip().upper() for x in args.tickers.split(',') if x.strip()]
    s = session()
    items = [parse_ticker(s, t, args.history_pages) for t in tickers]
    market_snapshot = None
    if args.include_stockonline:
        try:
            market_snapshot = parse_stockonline(s)
        except Exception as e:
            market_snapshot = {'status': 'error', 'error': str(e)}
    amibroker = None
    if args.download_amibroker != 'none':
        try:
            amibroker = parse_amibroker_zip(s, args.download_amibroker)
        except Exception as e:
            amibroker = {'status': 'error', 'error': str(e), 'type': args.download_amibroker}
    ok = all(i.get('status') == 'ok' for i in items) and (amibroker is None or amibroker.get('status') == 'ok')
    health = {
        'status': 'ok' if ok else 'partial',
        'ticker_count': len(items),
        'ok_ticker_count': sum(1 for i in items if i.get('status') == 'ok'),
        'history_rows': {i['ticker']: i.get('history', {}).get('row_count', 0) for i in items},
        'financial_rows': {i['ticker']: {k: v.get('row_count', 0) for k, v in i.get('financials', {}).items()} for i in items},
        'warnings': [w for i in items for w in i.get('warnings', [])],
    }
    out = {
        'as_of': now_iso(),
        'source': 'cophieu68.vn',
        'status': health['status'],
        'tickers': tickers,
        'items': items,
        'market_snapshot': market_snapshot,
        'amibroker_ohlcv': amibroker,
        'health_summary': health,
        'parse_quality': {'required_passed': ok, 'no_sample_fallback': True, 'raw_html_saved': str(RAW.relative_to(ROOT))},
    }
    save_json(LIVE / 'cophieu68_market_data.vn.json', out)
    save_json(LIVE / 'cophieu68_health.vn.json', health)
    print(json.dumps(health if args.summary else out, ensure_ascii=True, indent=2)[:12000])
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
