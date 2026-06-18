# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel('[新]校园订单详情_20260618_203119_2.xls')
fl = df[df['站点名称'].str.contains('分段履约', na=False)].copy()
pickup = fl[fl['物流单状态'] == '已取货'].copy()
pickup['下单时间_dt'] = pd.to_datetime(pickup['下单时间'], errors='coerce')

rider_cols = ['经手骑手1','经手骑手2','经手骑手3','经手骑手4','经手骑手5']
pickup['骑手数'] = pickup[rider_cols].notna().sum(axis=1)
pickup = pickup.sort_values(['站点名称','下单时间_dt'])

lines = []
lines.append('=== 配送中订单 (已取货) ===')
lines.append(f'总数: {len(pickup)}')
lines.append(f'数据拉取时间: 20:31')
lines.append('')

for s in sorted(pickup['站点名称'].unique()):
    sdf = pickup[pickup['站点名称'] == s]
    name = s.replace('分段履约广州', '')
    lines.append(f'--- {name} ({len(sdf)}单) ---')
    for _, row in sdf.iterrows():
        ot = row['下单时间_dt'].strftime('%H:%M') if pd.notna(row['下单时间_dt']) else '?'
        merchant = str(row['商家名'])[:24]
        amount = row['订单实付']
        r1 = str(row['经手骑手1']) if pd.notna(row['经手骑手1']) else '-'
        r2 = str(row['经手骑手2']) if pd.notna(row['经手骑手2']) else '-'
        r1t = pd.to_datetime(row['骑手1经手时间']).strftime('%H:%M') if pd.notna(row['骑手1经手时间']) else '-'
        r2t = pd.to_datetime(row['骑手2经手时间']).strftime('%H:%M') if pd.notna(row['骑手2经手时间']) else '-'
        category = row['配送品类']
        lines.append(f'  {ot} | {merchant:24s} | {amount:5.1f} | R1={r1:10s}@{r1t} | R2={r2:10s}@{r2t} | {category}')
    lines.append('')

# Summary
lines.append('--- 汇总 ---')
for s in sorted(pickup['站点名称'].unique()):
    sdf = pickup[pickup['站点名称'] == s]
    name = s.replace('分段履约广州', '')
    has_r2 = sdf['经手骑手2'].notna().sum()
    no_r2 = len(sdf) - has_r2
    lines.append(f'  {name}: {len(sdf)}单 (已分餐{has_r2}/未分餐{no_r2})')

report = '\n'.join(lines)
print(report)

with open('pickup_orders.txt', 'w', encoding='utf-8') as f:
    f.write(report)
print('\n[已保存] pickup_orders.txt')
