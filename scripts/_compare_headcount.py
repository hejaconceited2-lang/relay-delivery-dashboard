import pandas as pd
import os, glob, re, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
MT = os.path.join(BASE, '202606-艾云.xlsx')

# 1. Read MT station names
df_mt = pd.read_excel(MT, sheet_name=0, engine='calamine', header=0)
ID_TO_NAME = {}
for _, row in df_mt.iterrows():
    sid = int(row.iloc[1])
    name = row.iloc[2].replace('分段履约广州', '')
    ID_TO_NAME[sid] = name

def pdate(c):
    if not isinstance(c, (int, float)) or pd.isna(c): return None
    ci = int(c)
    if 20260601 <= ci <= 20260630:
        return (2026, (ci % 10000) // 100, ci % 100)
    return None

# 2. MT incentive headcount
df_inc = pd.read_excel(MT, sheet_name=1, engine='calamine', header=0)
mt = {}  # (sid, dt) -> headcount
for _, row in df_inc.iterrows():
    sid = int(row.iloc[0])
    if sid not in ID_TO_NAME: continue
    for c in df_inc.columns:
        dt = pdate(c)
        if dt:
            v = row[c]
            mt[(sid, dt)] = int(v) if pd.notna(v) else 0

# 3. Our data: registered headcount + orders per station per day
our_reg = {}
our_ord = {}
import datetime
for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try:
        m, d = int(parts[1]), int(parts[2])
        dt = (2026, m, d)
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
        cnt = len(sdf)
        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        our_reg[(sid, dt)] = len(riders)
        our_ord[(sid, dt)] = cnt

# 4. All dates
all_dates = sorted(set(k[1] for k in list(mt.keys()) + list(our_reg.keys())))

# 5. Print per station
for sid in sorted(ID_TO_NAME.keys()):
    name = ID_TO_NAME[sid]
    rows = []
    has_any = False
    for dt in all_dates:
        m = mt.get((sid, dt), 0)
        o_r = our_reg.get((sid, dt), 0)
        o_o = our_ord.get((sid, dt), 0)
        d_str = f'{dt[1]}/{dt[2]:02d}'
        rows.append((d_str, m, o_r, o_o, m != o_r))
        if m > 0 or o_r > 0:
            has_any = True

    if not has_any:
        continue

    # Count diff days
    diff_count = sum(1 for r in rows if r[4])
    # Find max diff
    max_diff = max((o_r - m for _, m, o_r, _, _ in rows if m != o_r), default=0)
    min_diff = min((o_r - m for _, m, o_r, _, _ in rows if m != o_r), default=0)

    print(f'\n=== {name} ({diff_count}天差异, 范围{min_diff:+d}~{max_diff:+d}) ===')
    print(f'{"日期":<7} {"美团激励":>8} {"我方登记":>8} {"我方订单":>8}  {"差异":>6}')
    print('-' * 42)
    printed = False
    for d_str, m, o_r, o_o, is_diff in rows:
        if m == 0 and o_r == 0:
            continue
        diff = o_r - m
        diff_s = f'+{diff}' if diff > 0 else str(diff)
        flag = ' ***' if is_diff else ''
        print(f'{d_str:<7} {m:>8} {o_r:>8} {o_o:>8} {diff_s:>6}{flag}')
        printed = True
    if not printed:
        print('  (无数据)')

# 6. Summary
print('\n' + '=' * 60)
print('汇总')
print('=' * 60)
total_mt = sum(mt.values())
total_our = sum(our_reg.values())
print(f'美团激励人次合计: {total_mt}')
print(f'我方登记人次合计: {total_our}')
print(f'差异: {total_our - total_mt:+d}')
