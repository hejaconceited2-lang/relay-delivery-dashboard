import pandas as pd
import os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
MT = os.path.join(BASE, '202606-艾云.xlsx')

df_mt = pd.read_excel(MT, sheet_name=0, engine='calamine', header=0)
ID_TO_NAME = {}
for _, row in df_mt.iterrows():
    ID_TO_NAME[int(row.iloc[1])] = row.iloc[2].replace('分段履约广州', '')

def pdate(c):
    if not isinstance(c, (int, float)) or pd.isna(c): return None
    ci = int(c)
    if 20260601 <= ci <= 20260630:
        return (2026, (ci % 10000) // 100, ci % 100)
    return None

# MT incentive
df_inc = pd.read_excel(MT, sheet_name=1, engine='calamine', header=0)
mt = {}
for _, row in df_inc.iterrows():
    sid = int(row.iloc[0])
    if sid not in ID_TO_NAME: continue
    for c in df_inc.columns:
        dt = pdate(c)
        if dt and pd.notna(row[c]):
            mt[(sid, dt)] = int(row[c])

# Our data
our_reg = {}
our_ord = {}
for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try:
        dt = (2026, int(parts[1]), int(parts[2]))
    except ValueError:
        continue
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()
    for s in df['站点名称'].unique():
        sids = df[df['站点名称'] == s]['站点ID'].dropna().unique()
        if not len(sids): continue
        sid = int(sids[0])
        if sid not in ID_TO_NAME: continue
        sdf = df[df['站点名称'] == s]
        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)

        # 补贴人数：达标时 = 登记人数-1，否则 = 0
        s_done = (sdf['物流单状态'] == '已送达').sum()
        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        per_p = s_kpi_done / registered if registered > 0 else 0
        subsidy_count = (registered - 1) if per_p >= 20 and registered > 1 else 0

        our_reg[(sid, dt)] = subsidy_count
        our_ord[(sid, dt)] = len(sdf)

all_keys = set()
for k in mt: all_keys.add(k[1])
for k in our_reg: all_keys.add(k[1])
all_dates = sorted(all_keys)

# Sort stations by volume
station_volume = {}
for sid in ID_TO_NAME:
    total = sum(our_ord.get((sid, dt), 0) for dt in all_dates)
    station_volume[sid] = total
sorted_stations = sorted(ID_TO_NAME.keys(), key=lambda s: -station_volume[s])

# Get station list (only those with data)
active_stations = []
for sid in sorted_stations:
    has = any(mt.get((sid, dt), 0) > 0 or our_reg.get((sid, dt), 0) > 0 for dt in all_dates)
    if has:
        active_stations.append(sid)

# ==== TABLE 1: Headcount comparison ====
print()
print('### 表1: 美团激励人数 / 我方登记人数')
print()

# Header
header = '| 站点 '
for dt in all_dates:
    header += f'| {dt[1]}/{dt[2]:02d} '
header += '| 差异天数 |'
print(header)

sep = '|' + '---|' * (len(all_dates) + 2)
print(sep)

for sid in active_stations:
    name = ID_TO_NAME[sid]
    row = f'| {name} '
    diff_days = 0
    for dt in all_dates:
        m = mt.get((sid, dt), 0)
        o = our_reg.get((sid, dt), 0)
        if m != o:
            diff_days += 1
        if m == 0 and o == 0:
            row += '| - '
        elif m != o:
            row += f'| **{m}/{o}** '
        else:
            row += f'| {m} '
    row += f'| {diff_days} |'
    print(row)

# Totals row
totals = '| 合计 '
for dt in all_dates:
    tm = sum(mt.get((sid, dt), 0) for sid in active_stations)
    to_reg = sum(our_reg.get((sid, dt), 0) for sid in active_stations)
    totals += f'| {tm}/{to_reg} '
totals += '| |'
print(totals)

# ==== TABLE 2: Headcount diff only (MT - Our) ====
print()
print('### 表2: 人数差异 (我方 - 美团)')
print()

header2 = '| 站点 '
for dt in all_dates:
    header2 += f'| {dt[1]}/{dt[2]:02d} '
header2 += '|'
print(header2)
print(sep)

for sid in active_stations:
    name = ID_TO_NAME[sid]
    row = f'| {name} '
    for dt in all_dates:
        m = mt.get((sid, dt), 0)
        o = our_reg.get((sid, dt), 0)
        diff = o - m
        if m == 0 and o == 0:
            row += '| '
        elif diff == 0:
            row += f'| 0 '
        else:
            row += f'| **+{diff}** '
    print(row + '|')

# ==== TABLE 3: Orders ====
print()
print('### 表3: 我方订单量')
print()

header3 = '| 站点 '
for dt in all_dates:
    header3 += f'| {dt[1]}/{dt[2]:02d} '
header3 += '| 月合计 |'
print(header3)
print('|' + '---|' * (len(all_dates) + 2))

for sid in active_stations:
    name = ID_TO_NAME[sid]
    row = f'| {name} '
    total_ord = 0
    for dt in all_dates:
        o = our_ord.get((sid, dt), 0)
        total_ord += o
        if o == 0:
            row += '| '
        else:
            row += f'| {o} '
    row += f'| **{total_ord}** |'
    print(row)

# Daily totals
daily_row = '| 日合计 '
grand = 0
for dt in all_dates:
    td = sum(our_ord.get((sid, dt), 0) for sid in active_stations)
    grand += td
    daily_row += f'| {td} '
print(daily_row + f'| **{grand}** |')

# ==== TABLE 4: Summary ====
print()
print('### 表4: 月度汇总')
print()
print('| 站点 | 差异天数 | 美团激励人次 | 我方补贴人次 | 差额 | 月订单量 |')
print('|------|:----:|:----:|:----:|:----:|:----:|')
mt_total_all = 0
our_total_all = 0
ord_total_all = 0
for sid in active_stations:
    name = ID_TO_NAME[sid]
    mt_t = sum(mt.get((sid, dt), 0) for dt in all_dates)
    our_t = sum(our_reg.get((sid, dt), 0) for dt in all_dates)
    ord_t = sum(our_ord.get((sid, dt), 0) for dt in all_dates)
    diff_days = sum(1 for dt in all_dates if mt.get((sid, dt), 0) != our_reg.get((sid, dt), 0))
    mt_total_all += mt_t
    our_total_all += our_t
    ord_total_all += ord_t
    print(f'| {name} | {diff_days} | {mt_t} | {our_t} | +{our_t-mt_t} | {ord_t} |')
print(f'| **合计** | | **{mt_total_all}** | **{our_total_all}** | **+{our_total_all-mt_total_all}** | **{ord_total_all}** |')
