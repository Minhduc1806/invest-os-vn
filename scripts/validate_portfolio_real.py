#!/usr/bin/env python
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/'data_live'/'portfolio_real.json'; out=ROOT/'outputs'/'portfolio_real_status.json'
d=json.loads(p.read_text(encoding='utf-8'))
nav=d.get('cash_vnd',0)+sum(x.get('quantity',0)*x.get('last_price',0) for x in d.get('positions',[]))-d.get('margin_debt_vnd',0)
valid=nav>0 and any(x.get('quantity',0)>0 and x.get('last_price',0)>0 for x in d.get('positions',[]))
res={'source':'validate_portfolio_real','valid':valid,'nav_vnd':nav,'message':'portfolio_real.json đã có NAV thật' if valid else 'portfolio_real.json vẫn template/zero NAV; cần nhập mã, số lượng, giá vốn, giá hiện tại, cash, margin_debt, risk_profile'}
out.write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
print(res['message'])
if not valid: sys.exit(2)
