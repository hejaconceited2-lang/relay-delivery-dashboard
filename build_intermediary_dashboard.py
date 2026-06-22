"""
绿地星玥 + 珠江国际 · 中间承包商合并看板
分账模式: 公司50% / 中间商50%
实际承包商: ¥2/完成单, 餐损全责
"""
import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════
# 站点配置
# ══════════════════════════════════════════
STATIONS = {
    '绿地星玥': {
        'file': 'lvdi_all_data.json',
        'staff': 4, 'labor_rate': 23, 'hours': 10, 'color': '#34d399', 'icon': '🌿',
    },
    '珠江国际轻纺城': {
        'file': 'zhujiang_all_data.json',
        'staff': 3, 'labor_rate': 30, 'hours': 3, 'color': '#fbbf24', 'icon': '🏭',
    },
}

SETTLE = 2.5; RIDER_FEE = 1.0; MATERIAL = 100/30
SUBSIDY_PER = 80; THRESHOLD = 20; ACTUAL_FEE = 2.0

def calc(data, cfg):
    rows = []
    for r in data:
        cnt = r['total']; done = r['done']
        riders = r['rider_count']
        pp = cnt / cfg['staff']
        meets = pp >= THRESHOLD
        revenue = cnt * (SETTLE + RIDER_FEE)
        subsidy = (cfg['staff'] - 1) * SUBSIDY_PER if meets else 0
        labor = riders * cfg['hours'] * cfg['labor_rate']
        actual_pay = done * ACTUAL_FEE
        cc = r['canc_comp']
        sp = revenue + subsidy - labor - MATERIAL - actual_pay
        rows.append({
            'date': r['date'], 'cnt': cnt, 'done': done, 'canc': r['canc'],
            'riders': riders, 'riders_list': r['riders'],
            'per_person': round(pp, 1), 'meets': meets,
            'revenue': round(revenue, 1), 'subsidy': round(subsidy, 1),
            'labor': round(labor, 1), 'material': round(MATERIAL, 1),
            'actual_pay': round(actual_pay, 1), 'canc_comp': round(cc, 1),
            'station_profit': round(sp, 1),
            'company': round(sp/2, 1), 'intermediary': round(sp/2, 1),
            'actual_profit': round(actual_pay - cc, 1),
        })
    return rows

all_rows = {}
summaries = {}
for name, cfg in STATIONS.items():
    with open(os.path.join(BASE_DIR, cfg['file']), 'r', encoding='utf-8') as f:
        raw = json.load(f)
    all_rows[name] = calc(raw, cfg)
    rows = all_rows[name]
    s = {
        'days': len(rows), 'total_orders': sum(d['cnt'] for d in rows),
        'total_done': sum(d['done'] for d in rows), 'total_canc': sum(d['canc'] for d in rows),
        'total_revenue': sum(d['revenue'] for d in rows),
        'total_subsidy': sum(d['subsidy'] for d in rows),
        'total_labor': sum(d['labor'] for d in rows),
        'total_material': sum(d['material'] for d in rows),
        'total_actual_pay': sum(d['actual_pay'] for d in rows),
        'total_canc_comp': sum(d['canc_comp'] for d in rows),
        'station': sum(d['station_profit'] for d in rows),
        'company': sum(d['company'] for d in rows),
        'intermediary': sum(d['intermediary'] for d in rows),
        'actual': sum(d['actual_profit'] for d in rows),
        'profitable_days': sum(1 for d in rows if d['intermediary'] > 0),
        'loss_days': sum(1 for d in rows if d['intermediary'] <= 0),
        'best': max(d['intermediary'] for d in rows),
        'best_date': rows[[d['intermediary'] for d in rows].index(max(d['intermediary'] for d in rows))]['date'],
        'worst': min(d['intermediary'] for d in rows),
        'worst_date': rows[[d['intermediary'] for d in rows].index(min(d['intermediary'] for d in rows))]['date'],
    }
    summaries[name] = s

now_str = datetime.now().strftime('%m-%d %H:%M')
total_both = summaries['绿地星玥']['intermediary'] + summaries['珠江国际轻纺城']['intermediary']

# ══════════════════════════════════════════
# 生成 HTML
# ══════════════════════════════════════════
def build_tab(name, rows, s, cfg, is_active):
    active_class = ' active' if is_active else ''
    flow_color = '#34d399' if s['intermediary'] >= 0 else '#f87171'
    icon = cfg['icon']
    color = cfg['color']
    short_id = 'lvdi' if name == '绿地星玥' else 'zhujiang'

    # 风险横幅
    alert = ''
    if s['intermediary'] < 0:
        alert = f'''
  <div class="alert-banner">
    <span style="font-size:20px">⚠️</span>
    <div><strong>{name}中间承包商{s['days']}天累计亏损 ¥{abs(s['intermediary']):,.0f}</strong>（日均 −¥{abs(s['intermediary']/s['days']):,.0f}）。仅{s['profitable_days']}/{s['days']}天盈利。{('06-15首日30单全部取消、餐损¥586，开局暴雷' if name=='珠江国际轻纺城' else '人力成本(5人×10h×23元=¥1,150/天)远超收入，06-22补贴未触发')}。</div>
  </div>'''

    # 三方流向卡片
    flow = f'''
  <div class="flow-box">
    <div class="flow-card" style="border-top:3px solid var(--accent)">
      <h3 style="color:var(--accent)">🏢 公司</h3>
      <div class="big" style="color:{'#34d399' if s['company']>=0 else '#f87171'}">{s['company']:+,.0f}</div>
      <div class="detail">站净利 50% 分账<br>日均 {s['company']/s['days']:+,.0f}</div>
    </div>
    <div class="flow-card" style="border-top:3px solid var(--purple)">
      <h3 style="color:var(--purple)">🔗 中间承包商</h3>
      <div class="big" style="color:{flow_color}">{s['intermediary']:+,.0f}</div>
      <div class="detail">站净利 50% 分账<br>日均 {s['intermediary']/s['days']:+,.0f} | {s['profitable_days']}/{s['days']}天盈利<br>零成本、零风险</div>
    </div>
    <div class="flow-card" style="border-top:3px solid var(--success)">
      <h3 style="color:var(--success)">🛵 实际承包商</h3>
      <div class="big" style="color:{'#34d399' if s['actual']>=0 else '#f87171'}">{s['actual']:+,.0f}</div>
      <div class="detail">{ACTUAL_FEE}/完成单 × {s['total_done']}单<br>餐损自负 −{s['total_canc_comp']:,.0f}<br>日均 {s['actual']/s['days']:+,.0f}</div>
    </div>
  </div>'''

    # KPI
    kpi = f'''
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-title">累计订单</div><div class="kpi-value" style="color:#818cf8">{s['total_orders']}</div><div class="kpi-sub">{s['days']}天 日均{s['total_orders']/s['days']:.0f}单</div></div>
    <div class="kpi-card"><div class="kpi-title">已完成 / 已取消</div><div class="kpi-value" style="color:#34d399">{s['total_done']}<span style="font-size:18px;color:#f87171">/{s['total_canc']}</span></div><div class="kpi-sub">完成率 {s['total_done']/s['total_orders']*100:.1f}%</div></div>
    <div class="kpi-card"><div class="kpi-title">中间承包商累计</div><div class="kpi-value" style="color:{flow_color}">{s['intermediary']:+,.0f}</div><div class="kpi-sub">日均 {s['intermediary']/s['days']:+,.0f} | 单均 {s['intermediary']/s['total_orders']:+.2f}</div></div>
    <div class="kpi-card"><div class="kpi-title">盈利天数</div><div class="kpi-value" style="color:#34d399">{s['profitable_days']}/{s['days']}</div><div class="kpi-sub">亏损 {s['loss_days']} 天</div></div>
    <div class="kpi-card"><div class="kpi-title">最好 / 最差</div><div class="kpi-value" style="color:#34d399">{s['best']:+,.0f}<span style="font-size:16px;color:#f87171"> / {s['worst']:+,.0f}</span></div><div class="kpi-sub">{s['best_date']} / {s['worst_date']}</div></div>
    <div class="kpi-card"><div class="kpi-title">实际承包商</div><div class="kpi-value" style="color:{'#34d399' if s['actual']>=0 else '#f87171'}">{s['actual']:+,.0f}</div><div class="kpi-sub">收入{s['total_actual_pay']:.0f} − 餐损{s['total_canc_comp']:.0f}</div></div>
  </div>'''

    # 日明细表
    table_rows = ''
    for d in rows:
        pc = '#34d399' if d['intermediary'] >= 0 else '#f87171'
        meets_s = '<span style="color:#34d399">✓</span>' if d['meets'] else '<span style="color:#f87171">✗</span>'
        riders_str = ', '.join(d['riders_list']) if d['riders_list'] else '—'
        table_rows += f'''
    <tr>
      <td style="color:var(--text);font-weight:500">{d['date']}</td>
      <td>{d['cnt']}</td><td style="color:#34d399">{d['done']}</td><td style="color:#f87171">{d['canc']}</td>
      <td>{d['riders']}</td><td>{d['per_person']}</td><td>{meets_s}</td>
      <td>{d['revenue']:,.0f}</td>
      <td style="color:{'#34d399' if d['subsidy']>0 else '#64748b'}">{'+'+str(d['subsidy']) if d['subsidy']>0 else '0'}</td>
      <td style="color:#f87171">−{d['labor']:,.0f}</td>
      <td style="color:#f87171">−{d['actual_pay']:,.0f}</td>
      <td style="color:{pc}">{d['station_profit']:+,.0f}</td>
      <td style="color:{pc};font-weight:600">{d['intermediary']:+,.0f}</td>
      <td style="color:{'#34d399' if d['actual_profit']>=0 else '#f87171'}">{d['actual_profit']:+,.0f}</td>
      <td style="font-size:11px;color:var(--text-muted)">{riders_str}</td>
    </tr>'''

    table = f'''
  <div class="section"><h2>日明细</h2>
  <div style="max-height:500px;overflow:auto;">
  <table><thead><tr>
    <th>日期</th><th>单量</th><th>完成</th><th>取消</th><th>人数</th><th>人均</th><th>达标</th>
    <th>收入</th><th>补贴</th><th>人力</th><th>实际承包</th>
    <th>站净利</th><th style="color:var(--purple)">中间商50%</th><th>实商净利</th><th>骑手</th>
  </tr></thead><tbody>{table_rows}
  <tr class="total">
    <td>累计 ({s['days']}天)</td><td>{s['total_orders']}</td>
    <td style="color:#34d399">{s['total_done']}</td><td style="color:#f87171">{s['total_canc']}</td>
    <td>—</td><td>—</td><td>—</td>
    <td>{s['total_revenue']:,.0f}</td><td>{s['total_subsidy']:,.0f}</td>
    <td style="color:#f87171">−{s['total_labor']:,.0f}</td><td style="color:#f87171">−{s['total_actual_pay']:,.0f}</td>
    <td style="color:{'#34d399' if s['station']>=0 else '#f87171'}">{s['station']:+,.0f}</td>
    <td style="color:{flow_color};font-weight:600">{s['intermediary']:+,.0f}</td>
    <td style="color:{'#34d399' if s['actual']>=0 else '#f87171'}">{s['actual']:+,.0f}</td>
    <td>—</td>
  </tr></tbody></table></div></div>'''

    # 图表数据 (内嵌到 tab JS)
    dates_display = [f"{d['date'][5:7]}/{d['date'][8:10]}" for d in rows]
    cd = {
        'dates': dates_display,
        'intermediary': [d['intermediary'] for d in rows],
        'company': [d['company'] for d in rows],
        'actual': [d['actual_profit'] for d in rows],
        'station': [d['station_profit'] for d in rows],
        'revenue': [d['revenue'] for d in rows],
        'subsidy': [d['subsidy'] for d in rows],
        'labor': [d['labor'] for d in rows],
        'actual_pay': [d['actual_pay'] for d in rows],
        'per_person': [d['per_person'] for d in rows],
    }

    charts_html = f'''
  <div class="section"><h2>三方日净利对比</h2><div id="{short_id}_chart1" style="height:420px"></div></div>
  <div class="section"><h2>中间商净利 & 人均单量</h2><div id="{short_id}_chart2" style="height:400px"></div></div>
  <div class="section"><h2>站收支结构</h2><div id="{short_id}_chart3" style="height:380px"></div></div>'''

    return f'''
<div class="tab-panel{active_class}" id="tab_{short_id}">
{alert}
{flow}
{kpi}
{charts_html}
{table}
</div>''', cd

# 构建所有tab
tabs = []
all_cd = {}
for i, (name, cfg) in enumerate(STATIONS.items()):
    content, cd = build_tab(name, all_rows[name], summaries[name], cfg, i == 0)
    tabs.append(content)
    all_cd[name] = cd

# 汇总卡片
v1 = summaries['绿地星玥']['intermediary']
v2 = summaries['珠江国际轻纺城']['intermediary']
pc1 = '#34d399' if v1 >= 0 else '#f87171'
pc2 = '#34d399' if v2 >= 0 else '#f87171'

# Tab 按钮
tab_btns = ''
for i, (name, cfg) in enumerate(STATIONS.items()):
    active = ' active' if i == 0 else ''
    tab_btns += f'<button class="tab-btn{active}" onclick="switchTab(\'{name}\')">{cfg["icon"]} {name}</button>\n'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中间承包商分账看板 · 绿地星玥 + 珠江国际</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #06080d; --surface: rgba(15,20,30,0.75); --border: rgba(148,163,184,0.08);
  --border-glow: rgba(129,140,248,0.25); --text: #e2e8f0; --text-dim: #94a3b8;
  --text-muted: #64748b; --accent: #818cf8; --success: #34d399; --danger: #f87171;
  --warning: #fbbf24; --purple: #a78bfa; --radius: 12px; --radius-sm: 8px;
  --transition: 0.25s cubic-bezier(0.4,0,0.2,1);
}}
* {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ font-family:'Inter',-apple-system,'Microsoft YaHei','PingFang SC',sans-serif; background:var(--bg); color:var(--text); min-height:100vh; line-height:1.5; -webkit-font-smoothing:antialiased; }}
body::before {{ content:''; position:fixed; inset:0; z-index:-1; pointer-events:none;
  background: radial-gradient(ellipse 80% 60% at 20% 10%, rgba(167,139,250,0.06) 0%, transparent 60%),
              radial-gradient(ellipse 60% 50% at 80% 80%, rgba(52,211,153,0.04) 0%, transparent 60%),
              radial-gradient(ellipse 50% 40% at 50% 50%, rgba(248,113,113,0.03) 0%, transparent 60%); }}

.header {{ position:relative; background:linear-gradient(135deg,rgba(15,20,30,0.95),rgba(30,41,59,0.9)); border-bottom:1px solid var(--border); padding:24px 32px 16px; backdrop-filter:blur(20px); overflow:hidden; }}
.header::after {{ content:''; position:absolute; bottom:0; left:0; right:0; height:2px; background:linear-gradient(90deg,#34d399,var(--purple),var(--accent),var(--danger)); opacity:0.6; }}
.header h1 {{ font-size:24px; font-weight:800; letter-spacing:-0.5px; background:linear-gradient(135deg,#a78bfa 0%,#e2e8f0 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
.header .sub {{ font-size:12px; color:var(--text-dim); margin-top:4px; }}

.tab-bar {{ display:flex; gap:4px; padding:10px 32px 0; background:rgba(10,14,22,0.7); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }}
.tab-btn {{ padding:8px 20px; border-radius:8px 8px 0 0; border:none; outline:none; background:transparent; color:var(--text-dim); cursor:pointer; font-size:13px; font-weight:500; font-family:inherit; transition:all var(--transition); position:relative; }}
.tab-btn::after {{ content:''; position:absolute; bottom:0; left:50%; transform:translateX(-50%); width:0; height:2px; background:var(--purple); border-radius:1px; transition:width var(--transition); }}
.tab-btn:hover {{ color:#e2e8f0; background:rgba(167,139,250,0.06); }}
.tab-btn.active {{ color:#e2e8f0; font-weight:600; background:rgba(167,139,250,0.1); }}
.tab-btn.active::after {{ width:80%; box-shadow:0 0 8px rgba(167,139,250,0.35); }}
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
.section h2::before {{ content:''; width:4px; height:18px; border-radius:2px; background:var(--purple); }}

.flow-box {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; margin-bottom:20px; }}
.flow-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:18px; text-align:center; }}
.flow-card h3 {{ font-size:14px; margin-bottom:10px; }}
.flow-card .big {{ font-size:28px; font-weight:800; margin:8px 0; }}
.flow-card .detail {{ font-size:11px; color:var(--text-muted); line-height:1.6; }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ background:rgba(30,41,59,0.6); color:var(--text-dim); font-weight:600; padding:9px 10px; text-align:left; font-size:10.5px; text-transform:uppercase; }}
td {{ padding:7px 10px; border-bottom:1px solid rgba(148,163,184,0.06); color:var(--text-dim); }}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:rgba(167,139,250,0.04); }}
tr.total td {{ font-weight:700; color:var(--text); border-top:1px solid rgba(148,163,184,0.2); }}

.alert-banner {{ background:rgba(248,113,113,0.08); border:1px solid rgba(248,113,113,0.2); border-radius:var(--radius-sm); padding:14px 18px; margin-bottom:16px; font-size:13px; color:#fca5a5; display:flex; align-items:center; gap:10px; line-height:1.6; }}
.note-box {{ background:rgba(167,139,250,0.06); border:1px solid rgba(167,139,250,0.15); border-left:3px solid var(--purple); padding:11px 16px; border-radius:var(--radius-sm); margin:14px 0; font-size:12px; color:var(--text-dim); line-height:1.7; }}
.note-box strong {{ color:var(--purple); }}

::-webkit-scrollbar {{ width:6px;height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:rgba(148,163,184,0.15); border-radius:3px; }}

@media (max-width:768px) {{
  .header {{ padding:16px 18px 10px; }} .header h1 {{ font-size:20px; }}
  .container {{ padding:12px 10px 30px; }} .flow-box {{ grid-template-columns:1fr; }}
  .summary-bar {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>中间承包商分账看板 · 绿地星玥 + 珠江国际</h1>
  <div class="sub">
    本地页面 &nbsp;·&nbsp;
    公司50% / 中间商50% / 实际承包商¥{ACTUAL_FEE}/单−餐损 &nbsp;·&nbsp;
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
      <div style="font-size:12px;color:var(--text-dim)">{summaries['绿地星玥']['days']}天 {summaries['绿地星玥']['total_orders']}单 | 中间商累计</div>
    </div>
    <div class="summary-card" onclick="switchTab('珠江国际轻纺城')">
      <h3 style="color:#fbbf24">🏭 珠江国际轻纺城</h3>
      <div class="val" style="color:{pc2}">{v2:+,.0f}</div>
      <div style="font-size:12px;color:var(--text-dim)">{summaries['珠江国际轻纺城']['days']}天 {summaries['珠江国际轻纺城']['total_orders']}单 | 中间商累计</div>
    </div>
  </div>

  <div class="note-box">
    <strong>分账规则</strong> &nbsp;
    收入 = 结算(¥{SETTLE}/单) + 骑手费(¥{RIDER_FEE}/单) + 补贴((T−1)×¥{SUBSIDY_PER}) &nbsp;|&nbsp;
    成本 = 人力 + 物料(¥{MATERIAL:.1f}/天) + 实际承包商费(¥{ACTUAL_FEE}×完成单) &nbsp;|&nbsp;
    站净利 → <b>公司50% / 中间商50%</b> &nbsp;|&nbsp;
    补贴门槛: 人均≥{THRESHOLD}单 且 ≥1人满3h
  </div>

  <div class="alert-banner"><span style="font-size:20px">⚠️</span><div><strong>两站中间商合计亏损 ¥{abs(total_both):,.0f}</strong>（绿地星玥 {v1:+,.0f} + 珠江国际 {v2:+,.0f}）。核心原因：人力成本刚性（绿地5人×10h=¥1,150/天）+ 补贴门槛难稳定达标 + 餐损波动大。当前三方分账模式下中间商无利可图。</div></div>

{''.join(tabs)}

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
  var t1a = {{ x: cd.dates, y: cd.company, type: 'bar', name: '公司 50%', marker: {{ color: '#818cf8' }}, text: cd.company.map(function(v){{ return '¥'+v; }}), textposition: 'outside', textfont: {{ color: '#c7d2fe', size: 9 }} }};
  var t1b = {{ x: cd.dates, y: cd.intermediary, type: 'bar', name: '中间商 50%', marker: {{ color: '#a78bfa' }}, text: cd.intermediary.map(function(v){{ return '¥'+v; }}), textposition: 'outside', textfont: {{ color: '#c4b5fd', size: 9 }} }};
  var t1c = {{ x: cd.dates, y: cd.actual, type: 'scatter', name: '实际承包商', mode: 'lines+markers', yaxis: 'y2', line: {{ color: '#34d399', width: 2 }}, marker: {{ size: 7, color: cd.actual.map(function(v){{ return v>=0?'#34d399':'#f87171'; }}) }} }};
  Plotly.newPlot(prefix+'_chart1', [t1a, t1b, t1c], {{
    barmode: 'group', title: '三方日净利对比', height: 420,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }}),
    yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, legend: dark.legend, hoverlabel: dark.hoverlabel,
  }}, cfg);

  var t2a = {{ x: cd.dates, y: cd.intermediary, type: 'bar', name: '中间商净利', marker: {{ color: cd.intermediary.map(function(v){{ return v>=0?'#34d399':'#f87171'; }}) }}, text: cd.intermediary.map(function(v){{ return '¥'+v; }}), textposition: 'outside', textfont: {{ color: '#e2e8f0', size: 9 }} }};
  var t2b = {{ x: cd.dates, y: cd.per_person, type: 'scatter', name: '人均单量', mode: 'lines+markers', yaxis: 'y2', line: {{ color: '#fbbf24', width: 2, dash: 'dot' }}, marker: {{ size: 8, color: '#fbbf24' }}, text: cd.per_person.map(function(v){{ return v+'单/人'; }}), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 9 }} }};
  Plotly.newPlot(prefix+'_chart2', [t2a, t2b], {{
    title: '中间商净利 & 人均单量', height: 400,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }}),
    yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, legend: dark.legend, hoverlabel: dark.hoverlabel,
    shapes: [{{ type: 'line', y0: 0, y1: 1, yref: 'paper', xref: 'paper', x0: 0, x1: 1, line: {{ color: '#fbbf24', dash: 'dash', width: 1 }} }}]
  }}, cfg);

  var income = cd.revenue.map(function(v,i){{ return v + cd.subsidy[i]; }});
  var cost = cd.labor.map(function(v,i){{ return v + 3.33 + cd.actual_pay[i]; }});
  var t3a = {{ x: cd.dates, y: income, type: 'bar', name: '收入+补贴', marker: {{ color: '#818cf8' }} }};
  var t3b = {{ x: cd.dates, y: cost.map(function(v){{ return -v; }}), type: 'bar', name: '人力+物料+承包', marker: {{ color: '#f87171' }} }};
  var t3c = {{ x: cd.dates, y: cd.station, type: 'scatter', name: '站净利', mode: 'lines+markers', line: {{ color: '#fbbf24', width: 2.5 }}, marker: {{ size: 8, color: cd.station.map(function(v){{ return v>=0?'#34d399':'#f87171'; }}) }}, text: cd.station.map(function(v){{ return '¥'+v; }}), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 9 }} }};
  Plotly.newPlot(prefix+'_chart3', [t3a, t3b, t3c], {{
    barmode: 'relative', title: '站收支结构', height: 380,
    xaxis: dark.xaxis, yaxis: Object.assign({{}}, dark.yaxis, {{ title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }}),
    paper_bgcolor: dark.paper_bgcolor, plot_bgcolor: dark.plot_bgcolor,
    font: dark.font, margin: dark.margin, legend: dark.legend, hoverlabel: dark.hoverlabel,
  }}, cfg);
}}

var cd_lvdi = {json.dumps(all_cd['绿地星玥'], ensure_ascii=False)};
var cd_zhujiang = {json.dumps(all_cd['珠江国际轻纺城'], ensure_ascii=False)};
makeCharts('lvdi', cd_lvdi);
makeCharts('zhujiang', cd_zhujiang);
</script>

</body>
</html>'''

output_path = os.path.join(BASE_DIR, 'lvdi_intermediary.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {output_path}')
for name in ['绿地星玥', '珠江国际轻纺城']:
    s = summaries[name]
    print(f'  {name}: {s["days"]}天 {s["total_orders"]}单 | 中间商{s["intermediary"]:+,.0f} | 实商{s["actual"]:+,.0f}')
print(f'  合计中间商: {total_both:+,.0f}')
