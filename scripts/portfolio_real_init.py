#!/usr/bin/env python
from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[1]; p=ROOT/'data_live'/'portfolio_real.json'; t=ROOT/'data_live'/'portfolio_real.template.json'
if not p.exists():
    shutil.copy(t,p)
    print('created',p,'from template; fill real holdings/cash/debt')
else:
    print('exists',p)
