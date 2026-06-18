# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_excel('[新]校园订单详情_20260618_203119_2.xls')
fl = df[df['站点名称'].str.contains('分段履约', na=False)].copy()
fl['下单时间_dt'] = pd.to_datetime(fl['下单时间'], errors='coerce')

print('--- File: 20260618_203119 (20:31 pull) ---')
print()

tmin = fl['下单时间_dt'].min()
tmax = fl['下单时间_dt'].max()
print('Total:', len(fl))
print('Time range:', str(tmin), '-', str(tmax))
print('Status:', fl['物流单状态'].value_counts().to_dict())
print()

print('Per station:')
for s in sorted(fl['站点名称'].unique()):
    sdf = fl[fl['站点名称'] == s]
    total = len(sdf)
    done = (sdf['物流单状态'] == '已送达').sum()
    canc = (sdf['物流单状态'] == '已取消').sum()
    pick = (sdf['物流单状态'] == '已取货').sum()
    name = s.replace('分段履约广州', '')
    print('  %s: %d (done=%d canc=%d pickup=%d)' % (name, total, done, canc, pick))
