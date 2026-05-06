#!/usr/bin/env python
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mod_path = ROOT / 'scripts' / 'refresh_news_live.py'
spec = importlib.util.spec_from_file_location('refresh_news_live', mod_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def check(label, cond):
    if not cond:
        raise AssertionError(label)
    print('OK', label)

def main() -> int:
    check('pnj good report', mod.is_real_news_link('PNJ investor relations', 'https://www.pnj.com.vn/quan-he-co-dong/bao-cao-tai-chinh/', 'Báo cáo tài chính'))
    check('pnj reject generic ir', not mod.is_real_news_link('PNJ investor relations', 'https://www.pnj.com.vn/quan-he-co-dong/dai-hoi-dong-co-dong/', 'Quan hệ cổ đông (IR)'))
    check('cafef reject generic ls', not mod.is_real_news_link('CafeF lãi suất - tỷ giá', 'https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn', 'Lãi suất ngân hàng'))
    check('cafef fallback title stable', mod.build_item('CafeF lãi suất - tỷ giá', 'https://cafef.vn/du-lieu/lai-suat-ngan-hang.chn', 'Lãi suất ngân hàng / tỷ giá CafeF')['title'] == 'Lãi suất ngân hàng / tỷ giá CafeF')
    check('vietstock reject lifestyle', not bool(mod.VIETSTOCK_GOOD_TITLE_RE.search('Doanh nhân và khởi nghiệp')))
    check('vietstock accept earnings', bool(mod.VIETSTOCK_GOOD_TITLE_RE.search('Kết quả kinh doanh quý 1/2026')))
    print('NEWS_TITLE_FILTER_TESTS_OK')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
