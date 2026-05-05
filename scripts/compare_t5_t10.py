import json
from pathlib import Path
p=Path('invest-os-vn/outputs/historical_backtest.json')
d=json.loads(p.read_text(encoding='utf-8'))
rows=[]
for tier in ['Tier A','Tier B']:
    s=d['summary'][tier]
    for h in ['T+5','T+10']:
        v=s[h]
        rows.append([tier,h,v['n'],v['avg_ret'],v['win_rate'],v['target_hit'],v['stop_hit'],v['avg_mae']])
md='# T+5 vs T+10 Comparison\n\n| Tier | Horizon | N | AvgRet % | Win % | Target % | Stop % | Avg MAE % |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n'
for r in rows:
    md+='| '+' | '.join(map(str,r))+' |\n'
A5=d['summary']['Tier A']['T+5']; A10=d['summary']['Tier A']['T+10']; B5=d['summary']['Tier B']['T+5']; B10=d['summary']['Tier B']['T+10']
md+=f"\n## Kết luận\n- Tier A: T+10 tốt hơn T+5 về avg return ({A10['avg_ret']}% vs {A5['avg_ret']}%) và win-rate ({A10['win_rate']}% vs {A5['win_rate']}%), nhưng MAE xấu hơn ({A10['avg_mae']}% vs {A5['avg_mae']}%).\n- Tier B: T+10 avg return cao hơn ({B10['avg_ret']}% vs {B5['avg_ret']}%), nhưng win-rate thấp hơn ({B10['win_rate']}% vs {B5['win_rate']}%) và stop hit cao hơn ({B10['stop_hit']}% vs {B5['stop_hit']}%).\n- Rule đề xuất: Tier A dùng T+10 làm holding window chính; Tier B dùng T+5 hoặc chỉ watch/confirm, không kéo tới T+10 nếu chưa lên Tier A.\n"
Path('invest-os-vn/outputs/t5_t10_comparison.md').write_text(md,encoding='utf-8')
Path('invest-os-vn/outputs/t5_t10_comparison.json').write_text(json.dumps({'rows':rows,'verdict':'Tier A T+10 better; Tier B T+5 safer'},ensure_ascii=False,indent=2),encoding='utf-8')
print(md)
