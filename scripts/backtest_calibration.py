#!/usr/bin/env python
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'
def main():
 d=json.loads((OUT/'historical_backtest.json').read_text(encoding='utf-8'))
 setup={r[0]:{'n':r[1],'t20_avg_ret':r[2],'win_rate':r[3]} for r in d.get('by_setup_T20',[])}
 sector={r[0]:{'n':r[1],'t20_avg_ret':r[2],'win_rate':r[3]} for r in d.get('by_sector_T20',[])}
 # convert backtest edge to scoring modifiers; no guessing, only data-derived from T+20 avg return/win-rate
 setup_mod={k:round(max(min(v['t20_avg_ret']*3 + (v['win_rate']-45)*0.4,12),-12),2) for k,v in setup.items() if v['n']>=100}
 sector_mod={k:round(max(min(v['t20_avg_ret']*2 + (v['win_rate']-45)*0.25,12),-12),2) for k,v in sector.items() if v['n']>=50}
 good_setups=[k for k,v in setup.items() if v['n']>=100 and v['t20_avg_ret']>1.5 and v['win_rate']>=48]
 weak_setups=[k for k,v in setup.items() if v['n']>=100 and (v['t20_avg_ret']<1.0 or v['win_rate']<45)]
 good_sectors=[k for k,v in sector.items() if v['n']>=50 and v['t20_avg_ret']>1.5 and v['win_rate']>=48]
 weak_sectors=[k for k,v in sector.items() if v['n']>=50 and (v['t20_avg_ret']<0 or v['win_rate']<40)]
 res={'source':'backtest_calibration','based_on':'historical_backtest by_setup_T20/by_sector_T20','setup_modifiers':setup_mod,'sector_modifiers':sector_mod,'preferred_setups':good_setups,'weak_setups':weak_setups,'preferred_sectors':good_sectors,'weak_sectors':weak_sectors,'tier_a_rule_hint':'Tier A should require backtest-positive setup/sector, not raw R/R only.'}
 (OUT/'backtest_calibration.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf-8')
 md='# Backtest Calibration\n\n## Preferred setups\n'+'\n'.join('- '+x for x in good_setups)+'\n\n## Weak setups\n'+'\n'.join('- '+x for x in weak_setups)+'\n\n## Preferred sectors\n'+'\n'.join('- '+x for x in good_sectors[:20])+'\n\n## Weak sectors\n'+'\n'.join('- '+x for x in weak_sectors[:20])
 (OUT/'backtest_calibration.md').write_text(md,encoding='utf-8')
 print('OK backtest calibration')
if __name__=='__main__': main()
