"""生成补贴人员Excel - 格式参照艾云-人头激励"""
import pandas as pd
import os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
OUT = os.path.join(BASE, 'output', '我方-人头激励.xlsx')

# Station name → ID mapping (from our data)
EXCLUDE = {'新亚洲电子城', '孙逸仙北院', '新中国大厦'}

# Collect data: {full_name: {day: subsidy_people}}
data = {}  # {full_name: {day: people}}
id_map = {}  # {full_name: station_id}
has_order = {}  # {full_name: set of days}

for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try: day = int(parts[2])
    except ValueError: continue
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()

    for s in df['站点名称'].unique():
        short = s.replace('分段履约广州', '')
        if short in EXCLUDE:
            continue

        sdf = df[df['站点名称'] == s]
        sids = df[df['站点名称'] == s]['站点ID'].dropna().unique()
        if len(sids):
            id_map[s] = int(sids[0])

        if s not in data:
            data[s] = {}
            has_order[s] = set()

        cnt = len(sdf)
        if cnt > 0:
            has_order[s].add(day)

        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)

        if registered > 1:
            s_kpi = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
            per_p = s_kpi / registered
            if per_p >= 20:
                data[s][day] = registered - 1

# Build Excel rows
stations = sorted(data.keys(), key=lambda s: -sum(data[s].values()))

rows = []
for s in stations:
    sid = id_map.get(s, '')
    row = {'站点ID': sid, '站点名称': s}
    total = 0
    for d in range(1, 31):
        col_name = f'202606{d:02d}'
        v = data[s].get(d, 0)
        if d in has_order.get(s, set()) or v > 0:
            row[col_name] = v if v > 0 else 0
        else:
            row[col_name] = None  # Leave blank if no orders
        total += v
    row['合计'] = total
    rows.append(row)

df_out = pd.DataFrame(rows)

# Reorder columns
date_cols = [f'202606{d:02d}' for d in range(1, 31)]
df_out = df_out[['站点ID', '站点名称'] + date_cols + ['合计']]

# Write to Excel with formatting
with pd.ExcelWriter(OUT, engine='openpyxl') as writer:
    df_out.to_excel(writer, sheet_name='我方-人头激励', index=False)

print(f'Saved: {OUT}')
print(f'Rows: {len(rows)}, Total: {df_out["合计"].sum()}')
print()
print('Station summary:')
for _, r in df_out.iterrows():
    if r['合计'] > 0:
        print(f'  {r["站点名称"]}: {int(r["合计"])}')
