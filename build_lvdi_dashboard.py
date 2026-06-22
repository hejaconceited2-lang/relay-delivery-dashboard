"""
绿地星玥 + 珠江国际 · 实际承包商合并看板
结算: ¥2/完成单, 餐损全责
"""
import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTLE = 2.0

STATIONS = {
    '绿地星玥': {'file': 'lvdi_all_data.json', 'color': '#34d399', 'icon': '🌿'},
    '珠江国际轻纺城': {'file': 'zhujiang_all_data.json', 'color': '#fbbf24', 'icon': '🏭'},
}

def calc_station(data):
    rows = []
    for r in data:
        income = r['done'] * SETTLE
        profit = income - r['canc_comp']
        rows.append({
            'date': r['date'], 'total': r['total'], 'done': r['done'],
            'canc': r['canc'], 'pickup': r.get('pickup', 0),
            'canc_comp': r['canc_comp'], 'income': round(income, 1),
            'profit': round(profit, 1),
            'avg_time': r.get('avg_time'), 'median_time': r.get('median_time'),
            'max_time': r.get('max_time'), 'over60': r.get('over60', 0),
            'riders': r.get('riders', []), 'rider_count': r.get('rider_count', 0),
        })
    return rows

all_rows = {}
summaries = {}
for name, cfg in STATIONS.items():
    with open(os.path.join(BASE_DIR, cfg['file']), 'r', encoding='utf-8') as f:
        raw = json.load(f)
    rows = calc_station(raw)
    all_rows[name] = rows
    s = {
        'days': len(rows), 'total_orders': sum(r['total'] for r in rows),
        'total_done': sum(r['done'] for r in rows), 'total_canc': sum(r['canc'] for r in rows),
        'total_pickup': sum(r['pickup'] for r in rows),
        'total_comp': sum(r['canc_comp'] for r in rows),
        'income': sum(r['income'] for r in rows),
        'profit': sum(r['profit'] for r in rows),
        'profitable_days': sum(1 for r in rows if r['profit'] > 0),
        'loss_days': sum(1 for r in rows if r['profit'] <= 0),
        'best': max(r['profit'] for r in rows),
        'best_date': rows[[r['profit'] for r in rows].index(max(r['profit'] for r in rows))]['date'],
        'worst': min(r['profit'] for r in rows),
        'worst_date': rows[[r['profit'] for r in rows].index(min(r['profit'] for r in rows))]['date'],
    }
    summaries[name] = s

    # 骑手汇总
    rider_days = {}
    for r in rows:
        for rider in r['riders']:
            if rider not in rider_days:
                rider_days[rider] = []
            rider_days[rider].append(r['date'])
    s['rider_days'] = rider_days

now_str = datetime.now().strftime('%m-%d %H:%M')

# ══════════════════════════════════════════
# Build tab HTML
# ══════════════════════════════════════════
def build_tab(name, rows, s, is_active):
    active_class = ' active' if is_active else ''
    icon = STATIONS[name]['icon']
    short_id = 'lvdi' if name == '绿地星玥' else 'zhujiang'
    profit_color = '#34d399' if s['profit'] >= 0 else '#f87171'

    # 风险横幅
    alert = ''
    if s['profit'] < 0:
        reason = '06-13/14两天集中暴雷餐损¥2,871' if name == '绿地星玥' else '06-15首日30单全部取消、餐损¥586'
        alert = f'''
  <div class="alert-banner"><span style="font-size:20px">⚠️</span><div><strong>{name}承包商{s['days']}天累计亏损 ¥{abs(s['profit']):,.0f}</strong>（日均 −¥{abs(s['profit']/s['days']):,.0f}）。{reason}，吃掉全部利润。</div></div>'''

    # KPI
    kpi = f'''
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-title">累计订单</div><div class="kpi-value" style="color:#818cf8">{s['total_orders']}</div><div class="kpi-sub">{s['days']}天 日均{s['total_orders']/s['days']:.0f}单</div></div>
    <div class="kpi-card"><div class="kpi-title">已完成 / 已取消</div><div class="kpi-value" style="color:#34d399">{s['total_done']}<span style="font-size:18px;color:#f87171">/{s['total_canc']}</span></div><div class="kpi-sub">完成率 {s['total_done']/s['total_orders']*100:.1f}%</div></div>
    <div class="kpi-card"><div class="kpi-title">承包商收入</div><div class="kpi-value" style="color:#34d399">{s['income']:,.0f}</div><div class="kpi-sub">{s['total_done']}单 × ¥{SETTLE:.0f}/单</div></div>
    <div class="kpi-card"><div class="kpi-title">餐损赔偿</div><div class="kpi-value" style="color:#f87171">−{s['total_comp']:,.0f}</div><div class="kpi-sub">已取消订单实付金额</div></div>
    <div class="kpi-card"><div class="kpi-title">承包商净利</div><div class="kpi-value" style="color:{profit_color}">{s['profit']:+,.0f}</div><div class="kpi-sub">日均 {s['profit']/s['days']:+,.0f} | 单均 {s['profit']/s['total_orders']:+.2f}</div></div>
    <div class="kpi-card"><div class="kpi-title">盈利/亏损天数</div><div class="kpi-value" style="color:#34d399">{s['profitable_days']}<span style="font-size:16px;color:#f87171">/{s['loss_days']}</span></div><div class="kpi-sub">最好 {s['best_date']} {s['best']:+,.0f} | 最差 {s['worst_date']} {s['worst']:+,.0f}</div></div>
  </div>'''

    # 明细表
    table_rows = ''
    for d in rows:
        pc = '#34d399' if d['profit'] >= 0 else '#f87171'
        pct = d['done']/d['total']*100 if d['total'] else 0
        riders_str = ', '.join(d['riders']) if d['riders'] else '—'
        table_rows += f'''
    <tr>
      <td style="color:var(--text);font-weight:500">{d['date']}</td>
      <td>{d['total']}</td><td style="color:#34d399">{d['done']}</td><td style="color:#f87171">{d['canc']}</td>
      <td>{pct:.1f}%</td><td>{d['income']:,.0f}</td>
      <td style="color:#f87171">{('-'+str(d['canc_comp'])) if d['canc_comp']>0 else '0'}</td>
      <td style="color:{pc};font-weight:600">{d['profit']:+,.0f}</td>
      <td style="color:{pc}">{d['profit']/d['total']:+.2f}</td>
      <td style="font-size:11px;color:var(--text-muted)">{riders_str}</td>
    </tr>'''

    table = f'''
  <div class="section"><h2>日明细</h2>
  <div style="max-height:500px;overflow:auto;">
  <table><thead><tr>
    <th>日期</th><th>单量</th><th>完成</th><th>取消</th><th>完成率</th>
    <th>收入 ¥{SETTLE:.0f}/单</th><th>餐损</th><th>净利</th><th>单均净利</th><th>骑手</th>
  </tr></thead><tbody>{table_rows}
  <tr class="total">
    <td>累计 ({s['days']}天)</td><td>{s['total_orders']}</td>
    <td style="color:#34d399">{s['total_done']}</td><td style="color:#f87171">{s['total_canc']}</td>
    <td>{s['total_done']/s['total_orders']*100:.1f}%</td><td>{s['income']:,.0f}</td>
    <td style="color:#f87171">−{s['total_comp']:,.0f}</td>
    <td style="color:{profit_color};font-weight:600">{s['profit']:+,.0f}</td>
    <td>{s['profit']/s['total_orders']:+.2f}</td><td>—</td>
  </tr></tbody></table></div></div>'''

    # 骑手表
    rider_rows = ''
    for rider in sorted(s['rider_days'].keys(), key=lambda x: len(s['rider_days'][x]), reverse=True):
        dl = s['rider_days'][rider]
        rider_rows += f'<tr><td style="color:var(--text);font-weight:500">{rider}</td><td>{len(dl)}天</td><td style="font-size:11px;color:var(--text-muted)">{", ".join(d[5:] for d in dl)}</td></tr>\n'
    rider_table = f'''
  <div class="section"><h2>骑手出勤汇总</h2>
  <div style="max-height:300px;overflow:auto;">
  <table><thead><tr><th>骑手</th><th>出勤天数</th><th>出勤日期</th></tr></thead><tbody>{rider_rows}</tbody></table></div></div>'''

    # 图表数据
    dates_display = [f"{d['date'][5:7]}/{d['date'][8:10]}" for d in rows]
    cd = {
        'dates': dates_display,
        'orders': [d['total'] for d in rows],
        'done': [d['done'] for d in rows],
        'canc': [d['canc'] for d in rows],
        'comp': [d['canc_comp'] for d in rows],
        'income': [d['income'] for d in rows],
        'profit': [d['profit'] for d in rows],
        'avg_time': [d['avg_time'] if d['avg_time'] else 0 for d in rows],
    }

    charts = f'''
  <div class="section"><h2>日单量 · 完成 & 取消</h2><div id="{short_id}_chart1" style="height:380px"></div></div>
  <div class="section"><h2>日收入 & 净利</h2><div id="{short_id}_chart2" style="height:380px"></div></div>
  <div class="section"><h2>餐损分布</h2><div id="{short_id}_chart3" style="height:380px"></div></div>'''

    return f'''
<div class="tab-panel{active_class}" id="tab_{short_id}">
{alert}
{kpi}
{charts}
{table}
{rider_table}
</div>''', cd


# ══════════════════════════════════════════
# 生成 HTML
# ══════════════════════════════════════════
tabs_html = []
all_cd = {}
tab_btns = ''
for i, (name, cfg) in enumerate(STATIONS.items()):
    is_active = (i == 0)
    content, cd = build_tab(name, all_rows[name], summaries[name], is_active)
    tabs_html.append(content)
    all_cd[name] = cd
    active = ' active' if is_active else ''
    tab_btns += f'<button class="tab-btn{active}" onclick="switchTab(\'{name}\')">{cfg["icon"]} {name}</button>\n'

v1 = summaries['绿地星玥']['profit']
v2 = summaries['珠江国际轻纺城']['profit']
pc1 = '#34d399' if v1 >= 0 else '#f87171'
pc2 = '#34d399' if v2 >= 0 else '#f87171'
total_both = v1 + v2

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>实际承包商看板 · 绿地星玥 + 珠江国际</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #06080d; --surface: rgba(15,20,30,0.75); --border: rgba(148,163,184,0.08);
  --border-glow: rgba(129,140,248,0.25); --text: #e2e8f0; --text-dim: #94a3b8;
  --text-muted: #64748b; --accent: #818cf8; --success: #34d399; --danger: #f87171;
  --warning: #fbbf24; --radius: 12px; --radius-sm: 8px;
  --transition: 0.25s cubic-bezier(0.4,0,0.2,1);
}}
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ font-family:'Inter',-apple-system,'Microsoft YaHei','PingFang SC',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; line-height:1.5; -webkit-font-smoothing:antialiased; }}
body::before {{ content:''; position:fixed; inset:0; z-index:-1; pointer-events:none;
  background: radial-gradient(ellipse 80% 60% at 20% 10%, rgba(129,140,248,0.06) 0%, transparent 60%),
              radial-gradient(ellipse 60% 50% at 80% 80%, rgba(52,211,153,0.04) 0%, transparent 60%),
              radial-gradient(ellipse 50% 40% at 50% 50%, rgba(248,113,113,0.03) 0%, transparent 60%); }}

.header {{ position:relative; background:linear-gradient(135deg,rgba(15,20,30,0.95),rgba(30,41,59,0.9)); border-bottom:1px solid var(--border); padding:24px 32px 16px; backdrop-filter:blur(20px); overflow:hidden; }}
.header::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:2px; background:linear-gradient(90deg,#34d399,var(--accent),var(--warning),var(--danger)); opacity:0.6; }}
.header h1 {{ font-size:24px; font-weight:800; letter-spacing:-0.5px; background:linear-gradient(135deg,#34d399 0%,#e2e8f0 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.header .sub {{ font-size:12px; color:var(--text-dim); margin-top:4px; }}

.tab-bar {{ display:flex; gap:4px; padding:10px 32px 0; background:rgba(10,14,22,0.7); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }}
.tab-btn {{ padding:8px 20px; border-radius:8px 8px 0 0; border:none; outline:none; background:transparent; color:var(--text-dim); cursor:pointer; font-size:13px; font-weight:500; font-family:inherit; transition:all var(--transition); position:relative; }}
.tab-btn::after {{ content:''; position:absolute; bottom:0; left:50%; transform:translateX(-50%); width:0; height:2px; background:var(--success); border-radius:1px; transition:width var(--transition); }}
.tab-btn:hover {{ color:#e2e8f0; background:rgba(52,211,153,0.06); }}
.tab-btn.active {{ color:#e2e8f0; font-weight:600; background:rgba(52,211,153,0.1); }}
.tab-btn.active::after {{ width:80%; box-shadow:0 0 8px rgba(52,211,153,0.35); }}
.tab-panel {{ display:none; animation:fadeSlideIn 0.35s ease; }}
.tab-panel.active {{ display:block; }}
@keyframes fadeSlideIn {{ from{{ opacity:0; transform:translateY(8px); }} to{{ opacity:1; transform:translateY(0); }} }}

.container {{ max-width:1240px; margin:0 auto; padding:20px 28px 40px; }}

.summary-bar {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }}
.summary-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; text-align:center; cursor:pointer; transition:all var(--transition); }}
.summary-card:hover {{ border-color:var(--border-glow); transform:translateY(-2px); }}
.summary-card h3 {{ font-size:14px; margin-bottom:8px; }}
.summary-card .val {{ font-size:32px; font-weight:800; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-bottom:20px; }}
.kpi-card {{ position:relative; overflow:hidden; background:var(--surface); backdrop-filter:blur(16px); border:1px solid var(--border); border-radius:var(--radius); padding:16px 18px; transition:all var(--transition); }}
.kpi-card:hover {{ transform:translateY(-2px); border-color:var(--border-glow); box-shadow:0 8px 32px rgba(0,0,0,0.3); }}
.kpi-title {{ font-size:10.5px; color:var(--text-muted); font-weight:600; text-transform:uppercase; letter-spacing:0.8px; }}
.kpi-value {{ font-size:26px; font-weight:800; margin:3px 0; font-variant-numeric:tabular-nums; letter-spacing:-1px; }}
.kpi-sub {{ font-size:11px; color:var(--text-dim); }}

.section {{ background:var(--surface); backdrop-filter:blur(20px); border:1px solid var(--border); border-radius:var(--radius); padding:20px 22px; margin-bottom:16px; }}
.section h2 {{ font-size:15px; font-weight:700; color:var(--text); padding-bottom:10px; margin-bottom:14px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px; }}
.section h2::before {{ content:''; width:4px; height:18px; border-radius:2px; background:var(--success); }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:rgba(30,41,59,0.6); color:var(--text-dim); font-weight:600; padding:9px 10px; text-align:left; font-size:10.5px; text-transform:uppercase; }}
td {{ padding:7px 10px; border-bottom:1px solid rgba(148,163,184,0.06); color:var(--text-dim); }}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:rgba(52,211,153,0.04); }}
tr.total td {{ font-weight:700; color:var(--text); border-top:1px solid rgba(148,163,184,0.2); }}

.alert-banner {{ background:rgba(248,113,113,0.08); border:1px solid rgba(248,113,113,0.2); border-radius:var(--radius-sm); padding:14px 18px; margin-bottom:16px; font-size:13px; color:#fca5a5; display:flex; align-items:center; gap:10px; line-height:1.6; }}
.note-box {{ background:rgba(52,211,153,0.06); border:1px solid rgba(52,211,153,0.15); border-left:3px solid var(--success); padding:11px 16px; border-radius:var(--radius-sm); margin:14px 0; font-size:12px; color:var(--text-dim); line-height:1.7; }}
.note-box strong {{ color:var(--success); }}

::-webkit-scrollbar {{ width:6px;height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:rgba(148,163,184,0.15); border-radius:3px; }}

@media (max-width:768px) {{
  .header {{ padding:16px 18px 10px; }} .header h1 {{ font-size:20px; }}
  .container {{ padding:12px 10px 30px; }} .summary-bar {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>实际承包商看板 · 绿地星玥 + 珠江国际</h1>
  <div class="sub">
    本地页面 &nbsp;·&nbsp;
    结算 ¥{SETTLE:.0f}/完成单 &nbsp;·&nbsp;
    餐损全责 &nbsp;·&nbsp;
    {now_str}
  </div>
</div>

<div class="tab-bar">
{tab_btns}
</div>

<div class="container">

  <div class="summary-bar">
    <div class="summary-card" onclick="switchTab('绿地星玥')">
      <h3 style="color:#34d399">🌿 绿地星玥</h3>
      <div class="val" style="color:{pc1}">{v1:+,.0f}</div>
      <div style="font-size:12px;color:var(--text-dim)">{summaries['绿地星玥']['days']}天 {summaries['绿地星玥']['total_orders']}单 | 承包商净利</div>
    </div>
    <div class="summary-card" onclick="switchTab('珠江国际轻纺城')">
      <h3 style="color:#fbbf24">🏭 珠江国际轻纺城</h3>
      <div class="val" style="color:{pc2}">{v2:+,.0f}</div>
      <div style="font-size:12px;color:var(--text-dim)">{summaries['珠江国际轻纺城']['days']}天 {summaries['珠江国际轻纺城']['total_orders']}单 | 承包商净利</div>
    </div>
  </div>

  <div class="note-box">
    <strong>结算规则</strong> &nbsp; 每完成1单 → 承包商收入 ¥{SETTLE:.0f} &nbsp;|&nbsp; 已取消订单的顾客实付金额（餐损）= 承包商承担 &nbsp;|&nbsp; 承包商不需承担人力/物料等固定成本
  </div>

  <div class="alert-banner"><span style="font-size:20px">⚠️</span><div><strong>两站承包商合计: {total_both:+,.0f}</strong>（绿地星玥 {v1:+,.0f} + 珠江国际 {v2:+,.0f}）。核心风险：餐损暴雷（绿地06-13/14两天¥2,871 + 珠江06-15一天¥586），两次暴雷即可吃掉所有利润。</div></div>

{''.join(tabs_html)}

</div>

<script>
function switchTab(name) {{
  var targetId = name === '绿地星玥' ? 'lvdi' : 'zhujiang';
  document.querySelectorAll('.tab-panel').forEach(function(p) {{ p.classList.remove('active'); }});
  document.querySelectorAll('.tab-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  document.getElementById('tab_' + targetId).classList.add('active');
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    if (b.textContent.includes(name.substring(0,2))) b.classList.add('active');
  }});
  setTimeout(function() {{
    document.querySelectorAll('.js-plotly-plot').forEach(function(el) {{ if (el._plotly) Plotly.Plots.resize(el); }});
  }}, 150);
}}

var dark = {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ color: '#94a3b8', size: 11 }},
  xaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false, tickangle: -30 }},
  yaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false }},
  margin: {{ t: 40, b: 60, l: 55, r: 30 }},
  legend: {{ font: {{ color: '#94a3b8' }}, orientation: 'h', y: 1.12 }},
  hoverlabel: {{ bgcolor: '#1e293b', font_size: 12 }}, bargap: 0.2,
}};
var cfg = {{ displayModeBar: true, responsive: true, displaylogo: false, scrollZoom: false }};

function makeCharts(prefix, cd) {{
  // Chart 1: 日单量 stacked
  var t1a = {{ x: cd.dates, y: cd.done, type: 'bar', name: '已完成', marker: {{ color: '#34d399' }}, text: cd.done, textposition: 'outside', textfont: {{ color: '#6ee7b7', size: 10 }} }};
  var t1b = {{ x: cd.dates, y: cd.canc, type: 'bar', name: '已取消', marker: {{ color: '#f87171' }}, text: cd.canc.map(function(v){{ return v>0?v:''; }}), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 10 }} }};
  Plotly.newPlot(prefix+'_chart1', [t1a, t1b], {{
    barmode: 'stack', title: '日单量 · 完成 vs 取消', height: 380,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: null }}),
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, legend: dark.legend, hoverlabel: dark.hoverlabel,
  }}, cfg);

  // Chart 2: 收入 & 净利
  var t2a = {{ x: cd.dates, y: cd.income, type: 'bar', name: '收入 (¥{SETTLE:.0f}×完成)', marker: {{ color: '#818cf8' }}, text: cd.income.map(function(v){{ return '¥'+v; }}), textposition: 'outside', textfont: {{ color: '#c7d2fe', size: 9 }} }};
  var t2b = {{ x: cd.dates, y: cd.comp.map(function(v){{ return -v; }}), type: 'bar', name: '餐损', marker: {{ color: '#f87171' }}, text: cd.comp.map(function(v){{ return v>0?'-¥'+v:''; }}), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 9 }} }};
  var t2c = {{ x: cd.dates, y: cd.profit, type: 'scatter', name: '净利', mode: 'lines+markers+text', yaxis: 'y2', line: {{ color: '#fbbf24', width: 2.5 }}, marker: {{ size: 8, color: cd.profit.map(function(v){{ return v>=0?'#34d399':'#f87171'; }}) }}, text: cd.profit.map(function(v){{ return '¥'+v; }}), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 9 }} }};
  Plotly.newPlot(prefix+'_chart2', [t2a, t2b, t2c], {{
    barmode: 'relative', title: '日收入 & 净利', height: 380,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: null }}),
    yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, legend: dark.legend, hoverlabel: dark.hoverlabel,
  }}, cfg);

  // Chart 3: 餐损
  var t3 = {{ x: cd.dates, y: cd.comp, type: 'bar', name: '餐损', marker: {{ color: cd.comp.map(function(v){{ return v>500?'#ef4444':v>100?'#f87171':'#fb923c'; }}) }}, text: cd.comp.map(function(v){{ return v>0?'¥'+v.toFixed(0):'0'; }}), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 10 }} }};
  Plotly.newPlot(prefix+'_chart3', [t3], {{
    title: '日餐损赔偿金额', height: 380,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: '元', zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }}),
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, hoverlabel: dark.hoverlabel,
  }}, cfg);
}}

var cd_lvdi = {json.dumps(all_cd['绿地星玥'], ensure_ascii=False)};
var cd_zhujiang = {json.dumps(all_cd['珠江国际轻纺城'], ensure_ascii=False)};
makeCharts('lvdi', cd_lvdi);
makeCharts('zhujiang', cd_zhujiang);
</script>

</body>
</html>'''

output_path = os.path.join(BASE_DIR, 'lvdi_contractor.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {output_path}')
for name in ['绿地星玥', '珠江国际轻纺城']:
    s = summaries[name]
    print(f'  {name}: {s["days"]}天 {s["total_orders"]}单 | 承包商{s["profit"]:+,.0f} | 单均{s["profit"]/s["total_orders"]:+.2f}')
print(f'  合计: {total_both:+,.0f}')
