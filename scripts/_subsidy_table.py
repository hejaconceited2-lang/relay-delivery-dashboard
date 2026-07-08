import pandas as pd
import os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'

# Our data - subsidy per station per day
subsidy = {}
orders = {}
registered_all = {}
all_stations = set()
all_dates_set = set()

for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try:
        m, d = int(parts[1]), int(parts[2])
        dt = (m, d)
    except ValueError: continue
    all_dates_set.add(dt)
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()
    for s in df['站点名称'].unique():
        sids = df[df['站点名称'] == s]['站点ID'].dropna().unique()
        if not len(sids): continue
        sid = int(sids[0])
        sdf = df[df['站点名称'] == s]
        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)
        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        per_p = s_kpi_done / registered if registered > 0 else 0
        meets = per_p >= 20
        sub = (registered - 1) * 80 if meets and registered > 1 else 0
        cnt = len(sdf)

        name = s.replace('分段履约广州', '')
        all_stations.add(name)
        subsidy[(name, dt)] = sub
        orders[(name, dt)] = cnt
        registered_all[(name, dt)] = registered

all_dates = sorted(all_dates_set)
stations = sorted(all_stations, key=lambda x: -sum(orders.get((x, d), 0) for d in all_dates))

# Filter to stations that appear at least once
active_stations = [s for s in stations if any(orders.get((s, d), 0) > 0 for d in all_dates)]

print()
print('### 我方各站点日补贴金额 (¥)')
print()
print('| 站点', end='')
for dt in all_dates:
    print(f'| {dt[0]}/{dt[1]:02d} ', end='')
print('| 月合计 |')
print('|' + '---|' * (len(all_dates) + 2))

for s in active_stations:
    print(f'| {s} ', end='')
    total = 0
    for dt in all_dates:
        v = subsidy.get((s, dt), 0)
        total += v
        if v > 0:
            print(f'| **{v}** ', end='')
        else:
            # Show order count for context
            o = orders.get((s, dt), 0)
            if o > 0:
                print(f'| · ', end='')
            else:
                print('| ', end='')
    print(f'| **{total}** |')

# Total row
print('| 日合计 ', end='')
grand = 0
for dt in all_dates:
    d_sum = sum(subsidy.get((s, dt), 0) for s in active_stations)
    grand += d_sum
    print(f'| {d_sum} ', end='')
print(f'| **{grand}** |')

# Summary table
print()
print('### 补贴详细')
print()
print('| 站点 | 补贴天数 | 补贴人次 | 补贴金额 | 补贴日期 |')
print('|------|:----:|:----:|:----:|------|')
for s in active_stations:
    sub_days = []
    sub_total = 0
    sub_count = 0
    for dt in all_dates:
        v = subsidy.get((s, dt), 0)
        if v > 0:
            r = registered_all.get((s, dt), 0)
            sub_days.append(f'{dt[0]}/{dt[1]:02d}({r}人→¥{v})')
            sub_total += v
            sub_count += (r - 1)
    if sub_days:
        print(f'| {s} | {len(sub_days)} | {sub_count} | {sub_total} | {", ".join(sub_days)} |')
    else:
        print(f'| {s} | 0 | 0 | 0 | - |')
