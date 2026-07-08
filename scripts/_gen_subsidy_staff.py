"""生成补贴人员统计表 - 按日期×站点"""
import pandas as pd
import os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
OUT = os.path.join(BASE, 'output', 'subsidy_staff.html')

rows = []  # [{station, data: {day: {registered, kpi, per, subsidy_people}}}]
all_dates = set()

for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try: day = int(parts[2])
    except ValueError: continue
    all_dates.add(day)
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()

    for s in df['站点名称'].unique():
        sdf = df[df['站点名称'] == s]
        name = s.replace('分段履约广州', '')
        # 排除竞争方站点
        if name in ('新亚洲电子城', '孙逸仙北院', '新中国大厦'):
            continue
        cnt = len(sdf)

        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)

        s_done = (sdf['物流单状态'] == '已送达').sum()
        s_kpi = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        per_p = round(s_kpi / registered, 1) if registered > 0 else 0
        sub_people = (registered - 1) if per_p >= 20 and registered > 1 else 0

        rows.append({
            'station': name, 'day': day,
            'orders': cnt, 'done': s_done, 'kpi': s_kpi,
            'registered': registered, 'per': per_p,
            'sub_people': sub_people
        })

df_all = pd.DataFrame(rows)
sorted_dates = sorted(all_dates)

# Aggregate by station
stations = sorted(df_all['station'].unique(), key=lambda s: -df_all[df_all['station']==s]['sub_people'].sum())

# Build subsidy lookup: {station: {day: sub_people}}
sm = {}
for _, r in df_all.iterrows():
    sm.setdefault(r['station'], {})[r['day']] = r['sub_people']

grand = sum(r['sub_people'] for _, r in df_all.iterrows())

# Generate HTML
html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
html += '<meta charset="UTF-8">\n'
html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
html += '<title>接力送 · 补贴人员统计 | 2026年6月</title>\n'
html += '<style>\n'
html += ':root{--bg:#0f1419;--surface:#1a2332;--border:rgba(148,163,184,0.12);--text:#e2e8f0;--dim:#94a3b8;--green:#34d399;--gold:#f59e0b;--blue:#38bdf8}\n'
html += '*{margin:0;padding:0;box-sizing:border-box}\n'
html += 'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);padding:24px;line-height:1.5}\n'
html += 'h1{font-size:22px;margin-bottom:4px}h1 span{color:var(--gold)}\n'
html += '.sub{color:var(--dim);font-size:13px;margin-bottom:24px}\n'
html += '.wrap{overflow-x:auto;margin-bottom:24px}\n'
html += 'table{border-collapse:collapse;font-size:13px}\n'
html += 'th,td{padding:6px 10px;text-align:center;border:1px solid var(--border);white-space:nowrap}\n'
html += 'th{background:var(--surface);font-weight:600}\n'
html += 'th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--surface);z-index:2;font-weight:500}\n'
html += 'tr:hover td{background:rgba(56,189,248,0.06)}\n'
html += '.has{background:rgba(52,211,153,0.15);color:var(--green);font-weight:700}\n'
html += '.no{color:#475569}\n'
html += '.tfoot td{background:var(--surface);font-weight:700;border-top:2px solid var(--blue)}\n'
html += '.footer{color:var(--dim);font-size:12px;margin-top:24px;border-top:1px solid var(--border);padding-top:16px}\n'
html += '</style>\n</head>\n<body>\n'
html += '<h1>接力送 · <span>补贴人员统计</span></h1>\n'
html += '<div class="sub">2026年6月 | 补贴人员 = 人均考核≥20时 (登记人数−1)，否则 0</div>\n'
html += '<h2 style="color:var(--blue);font-size:16px;margin-top:24px">日补贴人员明细 (人)</h2>\n'
html += '<div class="wrap"><table>\n'

# Header
html += '<thead><tr><th>站点</th>'
for d in sorted_dates:
    html += f'<th>6/{d}</th>'
html += '<th>月合计</th></tr></thead><tbody>\n'

for s in stations:
    html += f'<tr><td>{s}</td>'
    stotal = 0
    for d in sorted_dates:
        v = sm.get(s, {}).get(d, 0)
        stotal += v
        # Check if station has orders on this day
        has_orders = any((r['station'] == s and r['day'] == d and r['orders'] > 0) for _, r in df_all.iterrows())
        if v > 0:
            html += f'<td class="has">{v}</td>'
        elif has_orders:
            html += '<td class="no">·</td>'
        else:
            html += '<td></td>'
    html += f'<td style="font-weight:700;color:var(--gold)">{stotal}</td></tr>\n'

# Total
html += '<tr class="tfoot"><td>日合计</td>'
for d in sorted_dates:
    ds = sum(sm.get(s, {}).get(d, 0) for s in stations)
    html += f'<td>{ds}</td>'
html += f'<td>{grand}</td></tr>\n'
html += '</tbody></table></div>\n'

# Detail table with full breakdown
html += '<h2 style="color:var(--blue);font-size:16px;margin-top:32px">达标日详细 (达标时的人均和登记人数)</h2>\n'
html += '<div class="wrap"><table>\n'
html += '<thead><tr><th>站点</th><th>日期</th><th>订单量</th><th>考核单量</th><th>登记人数</th><th>人均</th><th>补贴人数</th></tr></thead><tbody>\n'

for _, r in df_all.sort_values(['station', 'day']).iterrows():
    if r['sub_people'] > 0:
        html += f'<tr><td>{r["station"]}</td><td>6/{r["day"]}</td><td>{r["orders"]}</td><td>{r["kpi"]}</td><td>{r["registered"]}</td><td>{r["per"]}</td><td class="has">{r["sub_people"]}</td></tr>\n'

html += '</tbody></table></div>\n'
html += f'<div class="footer">补贴人员月合计: {grand} 人次 · 生成时间: 2026-07-08</div>\n'
html += '</body></html>'

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Saved: {OUT}')
print(f'Stations: {len(stations)}, Total subsidy-people: {grand}')
