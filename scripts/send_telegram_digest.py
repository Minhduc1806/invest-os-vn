#!/usr/bin/env python
"""Optional Telegram sender for outputs/telegram_digest.txt.
Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    token=os.environ.get('TELEGRAM_BOT_TOKEN'); chat=os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('TELEGRAM_SEND_SKIPPED missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID',file=sys.stderr); return 2
    text=(ROOT/'outputs'/'telegram_digest.txt').read_text(encoding='utf-8')
    data=urlencode({'chat_id':chat,'text':text,'disable_web_page_preview':'true'}).encode()
    req=Request(f'https://api.telegram.org/bot{token}/sendMessage',data=data,headers={'Content-Type':'application/x-www-form-urlencoded'})
    with urlopen(req,timeout=30) as r:
        print(r.read().decode('utf-8','replace'))
    return 0
if __name__=='__main__': raise SystemExit(main())
