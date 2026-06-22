"""
绿地星玥 · 中间承包商独立看板
分账模式: 公司50% / 中间商50%
实际承包商: ¥2/完成单, 餐损全责
"""
import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'lvdi_all_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

# ════════════════════════════════════
# 绿地星玥参数
# ════════════════════════════════════
SETTLE = 2.5
RIDER_FEE = 1.0
LABOR_RATE = 23
HOURS = 10
MATERIAL = 100 / 30
SUBSIDY_PER = 80
STAFF = 4          # 编制
THRESHOLD = 20     # 人均门槛
ACTUAL_FEE = 2.0   # 实际承包商结算/完成单

daily_rows = []
for r in data:
    cnt = r['total']
    done = r['done']
    canc = r['canc']
    riders = r['rider_count']
    per_person = cnt / STAFF
    meets = per_person >= THRESHOLD

    settlement = cnt * SETTLE
    rider_income = cnt * RIDER_FEE
    revenue = settlement + rider_income
    subsidy = (STAFF - 1) * SUBSIDY_PER if meets else 0
    labor = riders * HOURS * LABOR_RATE
    material = MATERIAL
    actual_pay = done * ACTUAL_FEE
    canc_comp = r['canc_comp']

    # 站净利 = 收入 + 补贴 - 人力 - 物料 - 实际承包商费用
    station_profit = revenue + subsidy - labor - material - actual_pay
    company = station_profit / 2
    intermediary = station_profit / 2
    actual_profit = actual_pay - canc_comp

    daily_rows.append({
        'date': r['date'],
        'cnt': cnt, 'done': done, 'canc': canc,
        'riders': riders, 'per_person': round(per_person, 1),
        'meets': meets,
        'settlement': round(settlement, 1),
        'rider_income': round(rider_income, 1),
        'subsidy': round(subsidy, 1),
        'labor': round(labor, 1),
        'material': round(material, 1),
        'actual_pay': round(actual_pay, 1),
        'canc_comp': round(canc_comp, 1),
        'station_profit': round(station_profit, 1),
        'company': round(company, 1),
        'intermediary': round(intermediary, 1),
        'actual_profit': round(actual_profit, 1),
        'riders_list': r['riders'],
    })

# 汇总
total_revenue = sum(d['settlement'] + d['rider_income'] for d in daily_rows)
total_subsidy = sum(d['subsidy'] for d in daily_rows)
total_labor = sum(d['labor'] for d in daily_rows)
total_material = sum(d['material'] for d in daily_rows)
total_actual_pay = sum(d['actual_pay'] for d in daily_rows)
total_canc_comp = sum(d['canc_comp'] for d in daily_rows)
total_station = sum(d['station_profit'] for d in daily_rows)
total_company = sum(d['company'] for d in daily_rows)
total_intermediary = sum(d['intermediary'] for d in daily_rows)
total_actual = sum(d['actual_profit'] for d in daily_rows)
days = len(daily_rows)

# 用于图表
dates_display = [f"{d['date'][5:7]}/{d['date'][8:10]}" for d in daily_rows]
daily_intermediary = [d['intermediary'] for d in daily_rows]
daily_company = [d['company'] for d in daily_rows]
daily_actual = [d['actual_profit'] for d in daily_rows]
daily_station = [d['station_profit'] for d in daily_rows]
daily_labor = [d['labor'] for d in daily_rows]
daily_subsidy = [d['subsidy'] for d in daily_rows]
daily_revenue = [d['settlement'] + d['rider_income'] for d in daily_rows]
daily_actual_pay = [d['actual_pay'] for d in daily_rows]
daily_per_person = [d['per_person'] for d in daily_rows]
daily_riders = [d['riders'] for d in daily_rows]

now_str = datetime.now().strftime('%m-%d %H:%M')

# ── 利润分级 ──
profitable_days = sum(1 for d in daily_rows if d['intermediary'] > 0)
loss_days = sum(1 for d in daily_rows if d['intermediary'] <= 0)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绿地星玥 · 中间承包商看板 (本地)</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #06080d;
  --surface: rgba(15, 20, 30, 0.75);
  --border: rgba(148, 163, 184, 0.08);
  --border-glow: rgba(129, 140, 248, 0.25);
  --text: #e2e8f0;
  --text-dim: #94a3b8;
  --text-muted: #64748b;
  --accent: #818cf8;
  --success: #34d399;
  --danger: #f87171;
  --warning: #fbbf24;
  --purple: #a78bfa;
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'Inter', -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif;
  background: var(--bg); color: var(--text);
  min-height: 100vh; line-height: 1.5; -webkit-font-smoothing: antialiased;
}}
body::before {{
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(167,139,250,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 80%, rgba(52,211,153,0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 50% 50%, rgba(248,113,113,0.03) 0%, transparent 60%);
}}
.header {{
  position: relative;
  background: linear-gradient(135deg, rgba(15,20,30,0.95), rgba(30,41,59,0.9));
  border-bottom: 1px solid var(--border); padding: 24px 32px 16px;
  backdrop-filter: blur(20px); overflow: hidden;
}}
.header::after {{
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--purple), var(--accent), var(--success), var(--danger));
  opacity: 0.6;
}}
.header h1 {{
  font-size: 24px; font-weight: 800; letter-spacing: -0.5px;
  background: linear-gradient(135deg, #a78bfa 0%, #e2e8f0 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}}
.header .sub {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; }}
.container {{ max-width: 1240px; margin: 0 auto; padding: 20px 28px 40px; }}

.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }}
.kpi-card {{
  position: relative; overflow: hidden; background: var(--surface);
  backdrop-filter: blur(16px); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 18px; transition: all var(--transition);
}}
.kpi-card:hover {{ transform: translateY(-2px); border-color: var(--border-glow); box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
.kpi-title {{ font-size: 10.5px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; }}
.kpi-value {{ font-size: 26px; font-weight: 800; margin: 3px 0; font-variant-numeric: tabular-nums; letter-spacing: -1px; }}
.kpi-sub {{ font-size: 11px; color: var(--text-dim); }}

.section {{
  background: var(--surface); backdrop-filter: blur(20px);
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 20px 22px; margin-bottom: 16px;
}}
.section h2 {{ font-size: 15px; font-weight: 700; color: var(--text); padding-bottom: 10px; margin-bottom: 14px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }}
.section h2::before {{ content: ''; width: 4px; height: 18px; border-radius: 2px; background: var(--purple); }}

.chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}

table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{ background: rgba(30,41,59,0.6); color: var(--text-dim); font-weight: 600; padding: 9px 10px; text-align: left; font-size: 10.5px; text-transform: uppercase; }}
td {{ padding: 7px 10px; border-bottom: 1px solid rgba(148,163,184,0.06); color: var(--text-dim); }}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(167,139,250,0.04); }}
tr.total td {{ font-weight: 700; color: var(--text); border-top: 1px solid rgba(148,163,184,0.2); }}

.note-box {{
  background: rgba(167,139,250,0.06); border: 1px solid rgba(167,139,250,0.15);
  border-left: 3px solid var(--purple); padding: 11px 16px;
  border-radius: var(--radius-sm); margin: 14px 0; font-size: 12px; color: var(--text-dim); line-height: 1.7;
}}
.note-box strong {{ color: var(--purple); }}
.note-box.danger {{ background: rgba(248,113,113,0.06); border-color: rgba(248,113,113,0.15); border-left-color: var(--danger); }}
.note-box.danger strong {{ color: var(--danger); }}

.alert-banner {{
  background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.2);
  border-radius: var(--radius-sm); padding: 14px 18px; margin-bottom: 16px;
  font-size: 13px; color: #fca5a5; display: flex; align-items: center; gap: 10px;
}}

.flow-box {{
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 20px;
}}
.flow-card {{
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 18px; text-align: center;
}}
.flow-card h3 {{ font-size: 14px; margin-bottom: 10px; }}
.flow-card .big {{ font-size: 28px; font-weight: 800; margin: 8px 0; }}
.flow-card .detail {{ font-size: 11px; color: var(--text-muted); line-height: 1.6; }}

::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,0.15); border-radius: 3px; }}

@media (max-width: 768px) {{
  .header {{ padding: 16px 18px 10px; }}
  .header h1 {{ font-size: 20px; }}
  .container {{ padding: 12px 10px 30px; }}
  .chart-grid {{ grid-template-columns: 1fr; }}
  .flow-box {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>绿地星玥 · 中间承包商分账看板</h1>
  <div class="sub">
    本地页面 &nbsp;·&nbsp;
    {daily_rows[0]['date']} ~ {daily_rows[-1]['date']} &nbsp;·&nbsp;
    {days}天 &nbsp;·&nbsp;
    编制{STAFF}人 &nbsp;·&nbsp;
    人力{LABOR_RATE}元/h×{HOURS}h &nbsp;·&nbsp;
    {now_str}
  </div>
</div>

<div class="container">

  <!-- 三方流向 -->
  <div class="flow-box">
    <div class="flow-card" style="border-top: 3px solid var(--accent);">
      <h3 style="color:var(--accent)">🏢 公司</h3>
      <div class="big" style="color:{'#34d399' if total_company >= 0 else '#f87171'}">¥{total_company:+,.0f}</div>
      <div class="detail">
        收入 ¥{total_revenue:,.0f} + 补贴 ¥{total_subsidy:,.0f}<br>
        − 人力 ¥{total_labor:,.0f} − 物料 ¥{total_material:,.0f}<br>
        − 实际承包 ¥{total_actual_pay:,.0f}<br>
        净利 ¥{total_station:,.0f} → <b>50% = ¥{total_company:,.0f}</b>
      </div>
    </div>
    <div class="flow-card" style="border-top: 3px solid var(--purple);">
      <h3 style="color:var(--purple)">🔗 中间承包商</h3>
      <div class="big" style="color:{'#34d399' if total_intermediary >= 0 else '#f87171'}">¥{total_intermediary:+,.0f}</div>
      <div class="detail">
        站净利 50% 分账<br>
        日均 ¥{total_intermediary/days:+,.0f}<br>
        {profitable_days}天盈利 / {loss_days}天亏损<br>
        零成本、零风险
      </div>
    </div>
    <div class="flow-card" style="border-top: 3px solid var(--success);">
      <h3 style="color:var(--success)">🛵 实际承包商</h3>
      <div class="big" style="color:{'#34d399' if total_actual >= 0 else '#f87171'}">¥{total_actual:+,.0f}</div>
      <div class="detail">
        ¥{ACTUAL_FEE}/完成单 × {sum(d['done'] for d in daily_rows)}单<br>
        餐损自负 −¥{total_canc_comp:,.0f}<br>
        日均 ¥{total_actual/days:+,.0f}
      </div>
    </div>
  </div>

  <!-- 关键警报 -->
  <div class="alert-banner">
    <span style="font-size:20px">⚠️</span>
    <div>
      <strong>中间承包商12天累计亏损 ¥{abs(total_intermediary):,.0f}</strong>（日均 −¥{abs(total_intermediary/days):.0f}）。
      根本原因：人力成本过高（5人×10h×23元=¥1,150/天）远超收入，且06-22补贴未触发（人均17.8单不达标）。
      仅06-12/13/14/21四天盈利。
    </div>
  </div>

  <!-- KPI -->
  <div class="kpi-grid">
    <div class="kpi-card"><div class="kpi-title">中间承包商累计</div><div class="kpi-value" style="color:{'#34d399' if total_intermediary >= 0 else '#f87171'}">¥{total_intermediary:+,.0f}</div><div class="kpi-sub">日均 ¥{total_intermediary/days:+,.0f}</div></div>
    <div class="kpi-card"><div class="kpi-title">盈利天数</div><div class="kpi-value" style="color:#34d399">{profitable_days}/{days}</div><div class="kpi-sub">亏损 {loss_days} 天</div></div>
    <div class="kpi-card"><div class="kpi-title">最好单日</div><div class="kpi-value" style="color:#34d399">¥{max(d['intermediary'] for d in daily_rows):+,.0f}</div><div class="kpi-sub">{daily_rows[[d['intermediary'] for d in daily_rows].index(max(d['intermediary'] for d in daily_rows))]['date']}</div></div>
    <div class="kpi-card"><div class="kpi-title">最差单日</div><div class="kpi-value" style="color:#f87171">¥{min(d['intermediary'] for d in daily_rows):+,.0f}</div><div class="kpi-sub">{daily_rows[[d['intermediary'] for d in daily_rows].index(min(d['intermediary'] for d in daily_rows))]['date']}</div></div>
    <div class="kpi-card"><div class="kpi-title">公司累计</div><div class="kpi-value" style="color:{'#34d399' if total_company >= 0 else '#f87171'}">¥{total_company:+,.0f}</div><div class="kpi-sub">50% 分账</div></div>
    <div class="kpi-card"><div class="kpi-title">实际承包商累计</div><div class="kpi-value" style="color:{'#34d399' if total_actual >= 0 else '#f87171'}">¥{total_actual:+,.0f}</div><div class="kpi-sub">¥2/单 − 餐损</div></div>
  </div>

  <div class="note-box">
    <strong>分账规则</strong><br>
    1. 站收入 = 结算(¥{SETTLE}/单) + 骑手费(¥{RIDER_FEE}/单) + 补贴((T-1)×¥{SUBSIDY_PER})<br>
    2. 站成本 = 人力(¥{LABOR_RATE}/h×{HOURS}h×实际人数) + 物料(¥{MATERIAL:.1f}/天) + 实际承包商费(¥{ACTUAL_FEE}×完成单)<br>
    3. 站净利 = 收入 − 成本 → <b>公司50% / 中间商50%</b><br>
    4. 实际承包商独立结算：¥{ACTUAL_FEE}/完成单 − 餐损全额自负<br>
    5. 补贴条件：人均≥{THRESHOLD}单 且 ≥1人满3h
  </div>

  <!-- 图表 -->
  <div class="section"><h2>三方日净利对比</h2><div id="chart_3party" style="height:420px"></div></div>

  <div class="section"><h2>中间承包商日净利 & 人均单量</h2><div id="chart_intermediary" style="height:400px"></div></div>

  <div class="section"><h2>站收支瀑布</h2><div id="chart_waterfall" style="height:380px"></div></div>

  <!-- 日明细 -->
  <div class="section">
    <h2>日明细</h2>
    <div style="max-height:500px;overflow:auto;">
    <table><thead><tr>
      <th>日期</th><th>单量</th><th>完成</th><th>取消</th><th>人数</th><th>人均</th><th>达标</th>
      <th>结算+骑手费</th><th>补贴</th><th>人力</th><th>实际承包</th>
      <th>站净利</th><th>公司50%</th><th style="color:var(--purple)">中间商50%</th>
      <th>实际承包商</th>
    </tr></thead><tbody>
'''

for d in daily_rows:
    pc = '#34d399' if d['intermediary'] >= 0 else '#f87171'
    meets_str = '<span style="color:#34d399">✓</span>' if d['meets'] else '<span style="color:#f87171">✗</span>'
    html += f'''    <tr>
      <td style="color:var(--text);font-weight:500">{d['date']}</td>
      <td>{d['cnt']}</td><td style="color:#34d399">{d['done']}</td><td style="color:#f87171">{d['canc']}</td>
      <td>{d['riders']}</td><td>{d['per_person']}</td><td>{meets_str}</td>
      <td>¥{d['settlement']+d['rider_income']:,.0f}</td>
      <td style="color:{'#34d399' if d['subsidy']>0 else '#64748b'}">{'+¥'+str(d['subsidy']) if d['subsidy']>0 else '0'}</td>
      <td style="color:#f87171">-¥{d['labor']:,.0f}</td>
      <td style="color:#f87171">-¥{d['actual_pay']:,.0f}</td>
      <td style="color:{'#34d399' if d['station_profit']>=0 else '#f87171'}">¥{d['station_profit']:+,.0f}</td>
      <td>¥{d['company']:+,.0f}</td>
      <td style="color:{pc};font-weight:600">¥{d['intermediary']:+,.0f}</td>
      <td style="color:{'#34d399' if d['actual_profit']>=0 else '#f87171'}">¥{d['actual_profit']:+,.0f}</td>
    </tr>
'''

html += f'''    <tr class="total">
      <td>累计</td><td>{sum(d['cnt'] for d in daily_rows)}</td>
      <td style="color:#34d399">{sum(d['done'] for d in daily_rows)}</td>
      <td style="color:#f87171">{sum(d['canc'] for d in daily_rows)}</td>
      <td>—</td><td>—</td><td>—</td>
      <td>¥{total_revenue:,.0f}</td>
      <td>¥{total_subsidy:,.0f}</td>
      <td style="color:#f87171">-¥{total_labor:,.0f}</td>
      <td style="color:#f87171">-¥{total_actual_pay:,.0f}</td>
      <td style="color:{'#34d399' if total_station>=0 else '#f87171'}">¥{total_station:+,.0f}</td>
      <td>¥{total_company:+,.0f}</td>
      <td style="color:{'#34d399' if total_intermediary>=0 else '#f87171'};font-weight:600">¥{total_intermediary:+,.0f}</td>
      <td style="color:{'#34d399' if total_actual>=0 else '#f87171'}">¥{total_actual:+,.0f}</td>
    </tr>
  </tbody></table></div></div>

  <div class="note-box danger">
    <strong>⚠ 中间承包商模式风险</strong><br>
    1. <b>利润完全依赖站净利</b>：站亏损时中间商同比例亏损，无保底。<br>
    2. <b>人力成本不可控</b>：06-22 5人上岗拿71单，人力¥1,150但收入仅¥248，站净利−¥1,047。<br>
    3. <b>补贴断崖风险</b>：人均掉到20单以下时瞬间损失¥240/天补贴，06-22就是例子。<br>
    4. <b>12天仅4天盈利</b>：盈利概率33%，中间商承担了与公司同等的经营风险。<br>
    5. <b>对比实际承包商</b>：实际承包商¥2/单+餐损自负的模式反而盈亏接近平衡（¥43），因为收入与单量挂钩更紧。
  </div>

</div>

<script>
const dates = {json.dumps(dates_display, ensure_ascii=False)};
const intermediary = {json.dumps(daily_intermediary)};
const company = {json.dumps(daily_company)};
const actual = {json.dumps(daily_actual)};
const station = {json.dumps(daily_station)};
const labor = {json.dumps(daily_labor)};
const subsidy = {json.dumps(daily_subsidy)};
const revenue = {json.dumps(daily_revenue)};
const actualPay = {json.dumps(daily_actual_pay)};
const perPerson = {json.dumps(daily_per_person)};
const riders = {json.dumps(daily_riders)};

const dark = {{
  paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ color: '#94a3b8', size: 11 }},
  xaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false }},
  yaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false }},
  margin: {{ t: 40, b: 60, l: 55, r: 30 }},
  legend: {{ font: {{ color: '#94a3b8' }}, orientation: 'h', y: 1.12 }},
  hoverlabel: {{ bgcolor: '#1e293b', font_size: 12 }},
  bargap: 0.2,
}};
const cfg = {{ displayModeBar: true, responsive: true, displaylogo: false, scrollZoom: false }};

// Chart 1: 三方净利对比
const t1a = {{ x: dates, y: company, type: 'bar', name: '公司 50%', marker: {{ color: '#818cf8' }}, text: company.map(v => '¥'+v), textposition: 'outside', textfont: {{ color: '#c7d2fe', size: 9 }} }};
const t1b = {{ x: dates, y: intermediary, type: 'bar', name: '中间商 50%', marker: {{ color: '#a78bfa' }}, text: intermediary.map(v => '¥'+v), textposition: 'outside', textfont: {{ color: '#c4b5fd', size: 9 }} }};
const t1c = {{ x: dates, y: actual, type: 'scatter', name: '实际承包商', mode: 'lines+markers', yaxis: 'y2', line: {{ color: '#34d399', width: 2 }}, marker: {{ size: 7, color: actual.map(v => v >= 0 ? '#34d399' : '#f87171') }} }};
Plotly.newPlot('chart_3party', [t1a, t1b, t1c], {{
  ...dark, barmode: 'group', title: '三方日净利对比', height: 420,
  yaxis: {{ ...dark.yaxis, title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }},
  yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
  xaxis: {{ ...dark.xaxis, tickangle: -30 }}
}}, cfg);

// Chart 2: 中间商净利 + 人均单量
const t2a = {{ x: dates, y: intermediary, type: 'bar', name: '中间商净利', marker: {{ color: intermediary.map(v => v >= 0 ? '#34d399' : '#f87171') }}, text: intermediary.map(v => '¥'+v), textposition: 'outside', textfont: {{ color: '#e2e8f0', size: 10 }} }};
const t2b = {{ x: dates, y: perPerson, type: 'scatter', name: '人均单量', mode: 'lines+markers', yaxis: 'y2', line: {{ color: '#fbbf24', width: 2, dash: 'dot' }}, marker: {{ size: 8, color: '#fbbf24' }}, text: perPerson.map(v => v+'单/人'), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 9 }} }};
Plotly.newPlot('chart_intermediary', [t2a, t2b], {{
  ...dark, title: '中间商净利 & 人均单量（虚线=20单补贴门槛）', height: 400,
  yaxis: {{ ...dark.yaxis, title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }},
  yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
  xaxis: {{ ...dark.xaxis, tickangle: -30 }},
  shapes: [{{ type: 'line', y0: 0, y1: 1, yref: 'paper', xref: 'paper', x0: 0, x1: 1, line: {{ color: '#fbbf24', dash: 'dash', width: 1 }} }}]
}}, cfg);

// Chart 3: Waterfall
const income = revenue.map((v, i) => v + subsidy[i]);
const totalCost = labor.map((v, i) => v + 3.33 + actualPay[i]);
const t3a = {{ x: dates, y: income, type: 'bar', name: '收入+补贴', marker: {{ color: '#818cf8' }} }};
const t3b = {{ x: dates, y: totalCost.map(v => -v), type: 'bar', name: '人力+物料+实际承包', marker: {{ color: '#f87171' }} }};
const t3c = {{ x: dates, y: station, type: 'scatter', name: '站净利', mode: 'lines+markers', line: {{ color: '#fbbf24', width: 2.5 }}, marker: {{ size: 8, color: station.map(v => v >= 0 ? '#34d399' : '#f87171') }}, text: station.map(v => '¥'+v), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 9 }} }};
Plotly.newPlot('chart_waterfall', [t3a, t3b, t3c], {{
  ...dark, barmode: 'relative', title: '站收支结构 (净利 = 公司+中间商分账池)', height: 380,
  yaxis: {{ ...dark.yaxis, title: null, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }},
  xaxis: {{ ...dark.xaxis, tickangle: -30 }}
}}, cfg);
</script>

</body>
</html>'''

output_path = os.path.join(BASE_DIR, 'lvdi_intermediary.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {output_path}')
print(f'     中间承包商累计: ¥{total_intermediary:+,.0f} / 日均 ¥{total_intermediary/days:+,.0f}')
print(f'     盈利{profitable_days}天 / 亏损{loss_days}天')
