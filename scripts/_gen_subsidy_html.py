"""生成补贴明细独立HTML文件"""
import pandas as pd
import os, glob, json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
OUT = os.path.join(BASE, 'output', 'subsidy_detail.html')

# Collect data
data = {}  # {station: {subs: [[day, people, amount], ...], has_order: [day, ...]}}
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
        if name in ('新亚洲电子城', '孙逸仙北院', '新中国大厦'):
            continue
        if name not in data:
            data[name] = {'subs': [], 'has_order': []}

        cnt = len(sdf)
        if cnt > 0:
            data[name]['has_order'].append(day)

        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)
        if registered <= 1: continue

        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        per_p = s_kpi_done / registered
        if per_p >= 20:
            amount = (registered - 1) * 80
            data[name]['subs'].append([day, registered, amount])

sorted_dates = sorted(all_dates)
stations = sorted(data.keys(), key=lambda x: -sum(s[2] for s in data[x]['subs']))

# Build HTML
html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · 补贴明细 | 2026年6月</title>
<style>
:root { --bg:#0f1419; --surface:#1a2332; --border:rgba(148,163,184,0.12); --text:#e2e8f0; --text-dim:#94a3b8; --gold:#f59e0b; --green:#34d399; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:var(--bg); color:var(--text); padding:24px; line-height:1.5; }
h1 { font-size:22px; margin-bottom:4px; } h1 span { color:var(--gold); }
.sub { color:var(--text-dim); font-size:13px; margin-bottom:24px; }
h2 { font-size:16px; margin:28px 0 12px; color:#38bdf8; }
.wrap { overflow-x:auto; margin-bottom:32px; }
table { border-collapse:collapse; width:max-content; min-width:100%; font-size:13px; }
th, td { padding:6px 10px; text-align:center; border:1px solid var(--border); white-space:nowrap; }
th { background:var(--surface); font-weight:600; }
th:first-child, td:first-child { text-align:left; position:sticky; left:0; background:var(--surface); z-index:2; font-weight:500; }
tr:hover td { background:rgba(56,189,248,0.06); }
.sub-cell { background:rgba(52,211,153,0.12); color:var(--green); font-weight:700; }
.no-sub { color:#475569; }
.total-row td { background:var(--surface); font-weight:700; border-top:2px solid #38bdf8; }
.cards { display:grid; grid-template-columns:repeat(auto-fill, minmax(340px, 1fr)); gap:12px; margin-bottom:24px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:14px 16px; }
.card .name { font-size:15px; font-weight:600; margin-bottom:6px; }
.card .amount { font-size:22px; font-weight:800; color:var(--gold); }
.card .detail { font-size:12px; color:var(--text-dim); margin-top:4px; }
.card .detail em { color:#38bdf8; font-weight:500; font-style:normal; }
.card.no-sub { opacity:0.4; } .card.no-sub .amount { color:var(--text-dim); }
.footer { color:var(--text-dim); font-size:12px; margin-top:32px; border-top:1px solid var(--border); padding-top:16px; }
</style>
</head>
<body>
<h1>接力送 · <span>补贴明细</span></h1>
<div class="sub">2026年6月 | 补贴金额 = (登记人数−1)×80元 | 达标条件: 人均考核单量≥20<br>考核单量=已送达且商家ID≠−1(排除第三方平台订单)</div>

<h2>日补贴金额 (¥)</h2>
<div class="wrap">
<table>
<thead><tr><th>站点</th>
'''

for d in sorted_dates:
    html += f'<th>6/{d}</th>'
html += '<th>月合计</th></tr></thead><tbody>'

# Build subsidy lookup
smap = {s: {d: 0 for d in sorted_dates} for s in stations}
for s in stations:
    for sub in data[s]['subs']:
        smap[s][sub[0]] = sub[2]

grand_total = 0
for s in stations:
    html += f'<tr><td>{s}</td>'
    stotal = 0
    for d in sorted_dates:
        v = smap[s][d]
        stotal += v
        if v > 0:
            html += f'<td class="sub-cell">¥{v}</td>'
        elif d in data[s]['has_order']:
            html += '<td class="no-sub">·</td>'
        else:
            html += '<td></td>'
    html += f'<td style="font-weight:700;color:var(--gold)">¥{stotal:,}</td></tr>'
    grand_total += stotal

# Daily totals
html += '<tr class="total-row"><td>日合计</td>'
for d in sorted_dates:
    ds = sum(smap[s][d] for s in stations)
    html += f'<td>¥{ds:,}</td>'
html += f'<td>¥{grand_total:,}</td></tr></tbody></table></div>'

# Cards
html += '<h2>月补贴汇总</h2><div class="cards">'
for s in stations:
    subs = data[s]['subs']
    total = sum(v[2] for v in subs)
    people = sum(v[1]-1 for v in subs)
    ndays = len(subs)
    if total == 0:
        html += f'<div class="card no-sub"><div class="name">{s}</div><div class="amount">¥0</div><div class="detail">未达标</div></div>'
    else:
        day_str = ', '.join(f'6/{v[0]}({v[1]}人→¥{v[2]})' for v in subs)
        html += f'<div class="card"><div class="name">{s}</div><div class="amount">¥{total:,}</div><div class="detail"><em>{ndays}天</em> · <em>{people}人次</em> · {day_str}</div></div>'
html += '</div>'

html += f'<div class="footer">生成时间: 2026-07-08 · 数据源: 26-06-07 至 26-06-30</div>'
html += '</body></html>'

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Saved: {OUT}')
print(f'Stations: {len(stations)}, Total subsidy: ¥{grand_total:,}')
