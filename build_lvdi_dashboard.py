"""
绿地星玥 · 承包商独立看板
结算: ¥2/完成单, 餐损全责
"""
import json, os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, 'lvdi_all_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)

# ── 汇总 ──
total_orders = sum(r['total'] for r in data)
total_done = sum(r['done'] for r in data)
total_canc = sum(r['canc'] for r in data)
total_pickup = sum(r['pickup'] for r in data)
total_comp = sum(r['canc_comp'] for r in data)
SETTLE = 2  # 元/完成单
income = total_done * SETTLE
profit = income - total_comp
completion_rate = total_done / total_orders * 100 if total_orders else 0

# 日数据用于chart
dates_display = [f"{r['date'][5:7]}/{r['date'][8:10]}" for r in data]
dates_full = [r['date'] for r in data]
daily_orders = [r['total'] for r in data]
daily_done = [r['done'] for r in data]
daily_canc = [r['canc'] for r in data]
daily_comp = [r['canc_comp'] for r in data]
daily_income = [r['done'] * SETTLE for r in data]
daily_profit = [r['done'] * SETTLE - r['canc_comp'] for r in data]
daily_riders = [r['rider_count'] for r in data]
daily_avg_time = [r['avg_time'] if r['avg_time'] else 0 for r in data]

# ── 骑手汇总 ──
rider_days = {}
for r in data:
    for rider in r['riders']:
        if rider not in rider_days:
            rider_days[rider] = []
        rider_days[rider].append(r['date'])

now_str = datetime.now().strftime('%m-%d %H:%M')

# 站点配置信息
OUR_STATIONS = 1  # 绿地星玥 = 1个站点

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绿地星玥 · 承包商看板</title>
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
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'Inter', -apple-system, 'Microsoft YaHei', 'PingFang SC', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

body::before {{
  content: ''; position: fixed; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(129,140,248,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 80%, rgba(52,211,153,0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 50% 50%, rgba(248,113,113,0.03) 0%, transparent 60%);
}}

.header {{
  position: relative;
  background: linear-gradient(135deg, rgba(15,20,30,0.95), rgba(30,41,59,0.9));
  border-bottom: 1px solid var(--border);
  padding: 24px 32px 16px;
  backdrop-filter: blur(20px);
  overflow: hidden;
}}
.header::after {{
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, #34d399, var(--accent), var(--warning), var(--danger));
  opacity: 0.6;
}}
.header h1 {{
  font-size: 24px; font-weight: 800; letter-spacing: -0.5px;
  background: linear-gradient(135deg, #34d399 0%, #e2e8f0 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header .sub {{
  font-size: 12px; color: var(--text-dim); margin-top: 4px;
}}
.header .back {{
  display: inline-block; margin-bottom: 6px; color: var(--accent);
  font-size: 12px; text-decoration: none; transition: color 0.2s;
}}
.header .back:hover {{ color: #a5b4fc; }}

.container {{ max-width: 1240px; margin: 0 auto; padding: 20px 28px 40px; }}

.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 20px;
}}
.kpi-card {{
  position: relative; overflow: hidden;
  background: var(--surface);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  transition: all var(--transition);
}}
.kpi-card:hover {{
  transform: translateY(-2px);
  border-color: var(--border-glow);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px var(--border-glow);
}}
.kpi-title {{
  font-size: 10.5px; color: var(--text-muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.8px;
}}
.kpi-value {{
  font-size: 26px; font-weight: 800; margin: 3px 0;
  font-variant-numeric: tabular-nums; letter-spacing: -1px;
}}
.kpi-sub {{ font-size: 11px; color: var(--text-dim); }}

.section {{
  background: var(--surface);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px; margin-bottom: 16px;
  transition: border-color var(--transition);
}}
.section:hover {{ border-color: rgba(148,163,184,0.15); }}
.section h2 {{
  font-size: 15px; font-weight: 700; color: var(--text);
  padding-bottom: 10px; margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}}
.section h2::before {{
  content: ''; width: 4px; height: 18px; border-radius: 2px;
  background: #34d399;
}}

.chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.chart-full {{ grid-column: 1 / -1; }}

table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{
  background: rgba(30,41,59,0.6); color: var(--text-dim); font-weight: 600;
  padding: 9px 10px; text-align: left; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.5px;
}}
td {{
  padding: 7px 10px; border-bottom: 1px solid rgba(148,163,184,0.06);
  color: var(--text-dim);
}}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(129,140,248,0.04); }}
tr.total td {{ font-weight: 700; color: var(--text); border-top: 1px solid rgba(148,163,184,0.2); }}
tr.total td:first-child {{ color: var(--accent); }}

.note-box {{
  background: rgba(129,140,248,0.06);
  border: 1px solid rgba(129,140,248,0.15);
  border-left: 3px solid var(--accent);
  padding: 11px 16px; border-radius: var(--radius-sm);
  margin: 14px 0; font-size: 12px; color: var(--text-dim);
  line-height: 1.7;
}}
.note-box strong {{ color: var(--accent); }}
.note-box.danger {{
  background: rgba(248,113,113,0.06);
  border-color: rgba(248,113,113,0.15);
  border-left-color: var(--danger);
}}
.note-box.danger strong {{ color: var(--danger); }}

.alert-banner {{
  background: rgba(248,113,113,0.08);
  border: 1px solid rgba(248,113,113,0.2);
  border-radius: var(--radius-sm);
  padding: 14px 18px; margin-bottom: 16px;
  font-size: 13px; color: #fca5a5;
  display: flex; align-items: center; gap: 10px;
}}
.alert-banner .icon {{ font-size: 20px; }}

.riders-tags {{
  display: flex; flex-wrap: wrap; gap: 4px;
}}
.rider-tag {{
  display: inline-block; padding: 2px 8px;
  border-radius: 12px; font-size: 11px;
  background: rgba(129,140,248,0.12); color: #a5b4fc;
  white-space: nowrap;
}}

::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: rgba(148,163,184,0.15); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(148,163,184,0.3); }}

@media (max-width: 768px) {{
  .header {{ padding: 16px 18px 10px; }}
  .header h1 {{ font-size: 20px; }}
  .container {{ padding: 12px 10px 30px; }}
  .chart-grid {{ grid-template-columns: 1fr; }}
  .kpi-grid {{ grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }}
}}
</style>
</head>
<body>

<div class="header">
  <a href="index.html" class="back">&larr; 返回接力送总览</a>
  <h1>绿地星玥 · 承包商独立看板</h1>
  <div class="sub">
    {data[0]['date']} ~ {data[-1]['date']} &nbsp;·&nbsp;
    {len(data)}天 &nbsp;·&nbsp;
    结算 ¥{SETTLE}/完成单 &nbsp;·&nbsp;
    餐损全责 &nbsp;·&nbsp;
    {now_str} 更新
  </div>
</div>

<div class="container">

  <!-- ⚠️ 关键发现 -->
  <div class="alert-banner">
    <span class="icon">⚠️</span>
    <div>
      <strong>12天累计仅盈利 ¥{profit:,.1f}</strong> — 两天集中暴雷（06-13/14）造成 ¥2,871 餐损，占累计餐损的 {2871.3/total_comp*100:.0f}%。
      排除这两天后，其余10天累计盈利 ¥{profit+2871.3:,.0f}。
    </div>
  </div>

  <!-- KPI卡片 -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">累计订单</div>
      <div class="kpi-value" style="color:#818cf8">{total_orders}</div>
      <div class="kpi-sub">日均 {total_orders/len(data):.0f} 单</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">已完成</div>
      <div class="kpi-value" style="color:#34d399">{total_done}</div>
      <div class="kpi-sub">完成率 {completion_rate:.1f}%</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">已取消</div>
      <div class="kpi-value" style="color:#f87171">{total_canc}</div>
      <div class="kpi-sub">取消率 {total_canc/total_orders*100:.1f}%</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">承包商收入</div>
      <div class="kpi-value" style="color:#34d399">¥{income:,.0f}</div>
      <div class="kpi-sub">{total_done}单 × ¥{SETTLE}/单</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">餐损赔偿</div>
      <div class="kpi-value" style="color:#f87171">-¥{total_comp:,.0f}</div>
      <div class="kpi-sub">已取消订单实付金额</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">承包商净利</div>
      <div class="kpi-value" style="color:{'#34d399' if profit >= 0 else '#f87171'}">¥{profit:+,.0f}</div>
      <div class="kpi-sub">单均 ¥{profit/total_orders:+.2f} | 日均 ¥{profit/len(data):+.0f}</div>
    </div>
  </div>

  <div class="note-box">
    <strong>结算规则</strong> &nbsp; 每完成1单 → 承包商收入 ¥2.00 &nbsp;|&nbsp;
    已取消订单的顾客实付金额（餐损）= 承包商承担 &nbsp;|&nbsp;
    承包商不需承担人力/物料等固定成本
  </div>

  <!-- 图表区 -->
  <div class="section">
    <h2>日单量 · 完成 & 取消</h2>
    <div id="chart_daily" style="height:380px"></div>
  </div>

  <div class="section">
    <h2>日收入 & 净利</h2>
    <div id="chart_profit" style="height:380px"></div>
  </div>

  <div class="section">
    <h2>餐损分布（关键风险点）</h2>
    <div id="chart_comp" style="height:380px"></div>
  </div>

  <div class="section">
    <h2>日配送时长趋势</h2>
    <div id="chart_time" style="height:320px"></div>
  </div>

  <!-- 日明细表 -->
  <div class="section">
    <h2>日明细</h2>
    <div style="max-height:500px;overflow:auto;">
    <table>
      <thead><tr>
        <th>日期</th><th>订单</th><th>完成</th><th>取消</th><th>完成率</th>
        <th>收入 ¥{SETTLE}/单</th><th>餐损</th><th>净利</th>
        <th>单均净利</th><th>骑手</th>
      </tr></thead>
      <tbody>
'''

# 日明细行
for r in data:
    d_income = r['done'] * SETTLE
    d_profit = d_income - r['canc_comp']
    pct = r['done']/r['total']*100 if r['total'] else 0
    pc = '#34d399' if d_profit >= 0 else '#f87171'
    riders_html = '<div class="riders-tags">' + ''.join(f'<span class="rider-tag">{rd}</span>' for rd in r['riders']) + '</div>'
    html += f'''      <tr>
        <td style="color:var(--text);font-weight:500">{r['date']}</td>
        <td>{r['total']}</td>
        <td style="color:#34d399">{r['done']}</td>
        <td style="color:#f87171">{r['canc']}</td>
        <td>{pct:.1f}%</td>
        <td>¥{d_income:,.1f}</td>
        <td style="color:#f87171">{('-¥'+str(r['canc_comp'])) if r['canc_comp'] > 0 else '¥0'}</td>
        <td style="color:{pc};font-weight:600">¥{d_profit:+,.1f}</td>
        <td style="color:{pc}">¥{d_profit/r['total']:+.2f}</td>
        <td>{riders_html}</td>
      </tr>
'''

# 汇总行
html += f'''      <tr class="total">
        <td>累计 ({len(data)}天)</td>
        <td>{total_orders}</td>
        <td style="color:#34d399">{total_done}</td>
        <td style="color:#f87171">{total_canc}</td>
        <td>{completion_rate:.1f}%</td>
        <td>¥{income:,.1f}</td>
        <td style="color:#f87171">-¥{total_comp:,.1f}</td>
        <td style="color:{'#34d399' if profit >= 0 else '#f87171'};font-weight:600">¥{profit:+,.1f}</td>
        <td>¥{profit/total_orders:+.2f}</td>
        <td>—</td>
      </tr>
    </tbody></table>
    </div>
  </div>

  <!-- 骑手出勤 -->
  <div class="section">
    <h2>骑手出勤汇总</h2>
    <div style="max-height:400px;overflow:auto;">
    <table>
      <thead><tr><th>骑手</th><th>出勤天数</th><th>出勤日期</th></tr></thead>
      <tbody>
'''

for rider in sorted(rider_days.keys(), key=lambda x: len(rider_days[x]), reverse=True):
    days_list = rider_days[rider]
    html += f'''      <tr>
        <td style="color:var(--text);font-weight:500">{rider}</td>
        <td>{len(days_list)}天</td>
        <td style="font-size:11px;color:var(--text-muted)">{', '.join(d[5:] for d in days_list)}</td>
      </tr>
'''

html += f'''      </tbody></table>
    </div>
  </div>

  <!-- 风险分析 -->
  <div class="note-box danger">
    <strong>⚠ 风险提示</strong><br>
    1. <b>06-13/14 两天餐损 ¥{2871.3:,.1f}</b>（58单+34单取消），占累计餐损90%，发生在单人配送的测试期。<br>
    2. 06-13 取消率达 27%，06-14 取消率 15%，远超其他日期（通常 &lt;5%）。<br>
    3. 承包商模式的核心风险在于<b>取消率</b>：每取消1单平均损失 ¥{total_comp/total_canc:.0f}。<br>
    4. 从06-15起稳定在 &le;3人配送后，取消率控制在 0-3%，日净利转正。<br>
    5. <b>12天净利润仅 ¥{profit:.0f}</b> — 按此趋势，月净利约 ¥{profit/len(data)*30:.0f}，利润微薄。
  </div>

  <div class="note-box">
    <strong>建议</strong><br>
    1. 若排除测试期异常，稳定期的日净利约 ¥{sum(r['done']*SETTLE - r['canc_comp'] for r in data[2:])/(len(data)-2):.0f}/天（06-15起），月净利约 ¥{sum(r['done']*SETTLE - r['canc_comp'] for r in data[2:])/(len(data)-2)*30:,.0f}。<br>
    2. 应考虑设置<b>餐损上限</b>（如日餐损超过 ¥50 部分由公司分担），保护承包商。<br>
    3. 或者改为<b>阶梯结算</b>：基础 ¥2/单 + 取消率&lt;3% 奖励 ¥0.5/单。
  </div>

</div>

<script>
const dates = {json.dumps(dates_display, ensure_ascii=False)};
const dailyOrders = {json.dumps(daily_orders)};
const dailyDone = {json.dumps(daily_done)};
const dailyCanc = {json.dumps(daily_canc)};
const dailyComp = {json.dumps(daily_comp)};
const dailyIncome = {json.dumps(daily_income)};
const dailyProfit = {json.dumps(daily_profit)};
const dailyAvgTime = {json.dumps(daily_avg_time)};

const darkLayout = {{
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ color: '#94a3b8', size: 11 }},
  xaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false }},
  yaxis: {{ gridcolor: 'rgba(148,163,184,0.08)', linecolor: 'rgba(148,163,184,0.15)', zeroline: false }},
  margin: {{ t: 40, b: 60, l: 55, r: 30 }},
  legend: {{ font: {{ color: '#94a3b8' }}, orientation: 'h', y: 1.12 }},
  hoverlabel: {{ bgcolor: '#1e293b', font_size: 12 }},
  bargap: 0.2,
}};

const config = {{ displayModeBar: true, responsive: true, displaylogo: false, scrollZoom: false }};

// Chart 1: 日单量 (stacked bar: 完成 + 取消)
const trace1a = {{ x: dates, y: dailyDone, type: 'bar', name: '已完成', marker: {{ color: '#34d399' }}, text: dailyDone, textposition: 'outside', textfont: {{ color: '#6ee7b7', size: 10 }} }};
const trace1b = {{ x: dates, y: dailyCanc, type: 'bar', name: '已取消', marker: {{ color: '#f87171' }}, text: dailyCanc.map(v => v > 0 ? v : ''), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 10 }} }};
Plotly.newPlot('chart_daily', [trace1a, trace1b], {{
  ...darkLayout, barmode: 'stack', title: '日单量 · 完成 vs 取消', height: 380,
  yaxis: {{ ...darkLayout.yaxis, title: null }},
  xaxis: {{ ...darkLayout.xaxis, tickangle: -30 }}
}}, config);

// Chart 2: 收入 & 净利
const profitColors = dailyProfit.map(v => v >= 0 ? '#34d399' : '#f87171');
const trace2a = {{ x: dates, y: dailyIncome, type: 'bar', name: '收入 (¥2×完成)', marker: {{ color: '#818cf8' }}, text: dailyIncome.map(v => '¥'+v), textposition: 'outside', textfont: {{ color: '#c7d2fe', size: 10 }} }};
const trace2b = {{ x: dates, y: dailyComp.map(v => -v), type: 'bar', name: '餐损', marker: {{ color: '#f87171' }}, text: dailyComp.map(v => v > 0 ? '-¥'+v : ''), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 10 }} }};
const trace2c = {{ x: dates, y: dailyProfit, type: 'scatter', name: '净利', mode: 'lines+markers+text', yaxis: 'y2', line: {{ color: '#fbbf24', width: 2.5 }}, marker: {{ size: 8, color: profitColors }}, text: dailyProfit.map(v => '¥'+v), textposition: 'top center', textfont: {{ color: '#fcd34d', size: 10 }} }};
Plotly.newPlot('chart_profit', [trace2a, trace2b, trace2c], {{
  ...darkLayout, barmode: 'relative', title: '日收入 & 净利', height: 380,
  yaxis: {{ ...darkLayout.yaxis, title: null }},
  yaxis2: {{ title: null, overlaying: 'y', side: 'right', showgrid: false }},
  xaxis: {{ ...darkLayout.xaxis, tickangle: -30 }}
}}, config);

// Chart 3: 餐损分布
const trace3 = {{ x: dates, y: dailyComp, type: 'bar', name: '餐损', marker: {{ color: dailyComp.map(v => v > 500 ? '#ef4444' : v > 100 ? '#f87171' : '#fb923c') }}, text: dailyComp.map(v => v > 0 ? '¥'+v.toFixed(0) : '0'), textposition: 'outside', textfont: {{ color: '#fca5a5', size: 10 }} }};
Plotly.newPlot('chart_comp', [trace3], {{
  ...darkLayout, title: '日餐损赔偿金额', height: 380,
  yaxis: {{ ...darkLayout.yaxis, title: '元', zeroline: true, zerolinecolor: 'rgba(148,163,184,0.15)' }},
  xaxis: {{ ...darkLayout.xaxis, tickangle: -30 }},
  shapes: [{{
    type: 'line', y0: 0, y1: 1, yref: 'paper',
    x0: 2.5, x1: 2.5, xref: 'x',
    line: {{ color: '#fbbf24', dash: 'dash', width: 1 }}
  }}]
}}, config);

// Chart 4: 配送时长
const trace4 = {{ x: dates, y: dailyAvgTime, type: 'scatter', name: '平均配送时长', mode: 'lines+markers', line: {{ color: '#818cf8', width: 2 }}, marker: {{ size: 6, color: '#a5b4fc' }}, text: dailyAvgTime.map(v => v.toFixed(0)+'min'), textposition: 'top center', textfont: {{ color: '#c7d2fe', size: 10 }} }};
Plotly.newPlot('chart_time', [trace4], {{
  ...darkLayout, title: '日均配送时长 (min)', height: 320,
  yaxis: {{ ...darkLayout.yaxis, title: '分钟', zeroline: false }},
  xaxis: {{ ...darkLayout.xaxis, tickangle: -30 }}
}}, config);
</script>

</body>
</html>'''

# 写入文件
output_path = os.path.join(BASE_DIR, 'lvdi_contractor.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {output_path}')
print(f'     1726单 / 12天 / 承包商净利 ¥{profit:,.1f} / 单均 ¥{profit/total_orders:+.2f}')
