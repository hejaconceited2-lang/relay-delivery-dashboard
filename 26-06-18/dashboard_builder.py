"""
接力送 · 运营看板  |  2026-06-18
数据截止 20:31（近全天），含已取货/已创建状态
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

INPUT = r"D:\CC\接力送日订单\26-06-18\[新]校园订单详情_20260618_203119_2.xls"
OUTPUT = r"D:\CC\接力送日订单\26-06-18\operations_dashboard.html"
INDEX_OUT = r"D:\CC\接力送日订单\26-06-18\index.html"

df = pd.read_excel(INPUT)
df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

# 预处理
df['下单时间_dt'] = pd.to_datetime(df['下单时间'], errors='coerce')
df['送达时间_dt'] = pd.to_datetime(df['送达时间'], errors='coerce')
df['hour'] = df['下单时间_dt'].dt.hour
mask_done = df['送达时间_dt'].notna()
df.loc[mask_done, '配送时长_min'] = (
    df.loc[mask_done, '送达时间_dt'] - df.loc[mask_done, '下单时间_dt']
).dt.total_seconds() / 60

rider_cols = ['经手骑手1', '经手骑手2', '经手骑手3', '经手骑手4', '经手骑手5']
df['rider_count'] = df[rider_cols].notna().sum(axis=1)

# 数据时间范围
t_min = df['下单时间_dt'].min()
t_max = df['下单时间_dt'].max()

# 分类
COMPETITORS = {'分段履约广州新中国大厦', '分段履约广州新亚洲电子城', '分段履约广州孙逸仙北院'}
df['归属'] = df['站点名称'].apply(lambda s: '竞争方' if s in COMPETITORS else '我方')

KNOWN_STAFF = {
    '分段履约广州绿地星玥': 5, '分段履约广州万菱广场': 2,
    '分段履约广州和业广场': 3, '分段履约广州金鹰大厦': 2,
    '分段履约广州华林国际C馆': 2, '分段履约广州中大附属第六医院': 6,
    '分段履约广州珠江国际轻纺城': 3,
    '分段履约广州孙逸仙北院': 2, '分段履约广州新亚洲电子城': 3,
    '分段履约广州新中国大厦': 3,
    '分段履约广州中大附三岭南医院': 2,
    '分段履约广州汇德国际': 2,
    '分段履约广州云升科技园': 2,
    '分段履约广州万科欧泊': 3,
}

# 全局汇总
total = len(df)
ours = df[df['归属'] == '我方']
comps = df[df['归属'] == '竞争方']
done = (df['物流单状态'] == '已送达').sum()
canc = (df['物流单状态'] == '已取消').sum()
pickup = (df['物流单状态'] == '已取货').sum()
avg_time = df.loc[mask_done, '配送时长_min'].mean()
median_time = df.loc[mask_done, '配送时长_min'].median()
peak_h = df['hour'].value_counts().idxmax()
peak_cnt = df['hour'].value_counts().max()

# 站点汇总
station_rows = []
for s in df['站点名称'].unique():
    sdf = df[df['站点名称'] == s]
    cnt = len(sdf)
    s_done = (sdf['物流单状态'] == '已送达').sum()
    s_canc = (sdf['物流单状态'] == '已取消').sum()
    s_pickup = (sdf['物流单状态'] == '已取货').sum()
    grp = sdf['归属'].iloc[0]
    staff = KNOWN_STAFF.get(s)
    per_person = cnt / staff if staff else None

    if staff and per_person:
        gap = 20 - per_person
        meets = per_person >= 20
        if meets:
            gap_label = f'达标 (+{(-gap):.0f}单)'
        else:
            gap_label = f'还差 {gap:.0f} 单'
    else:
        gap = None
        meets = False
        gap_label = '编制未知' if staff is None else '?'

    s_times = sdf.loc[sdf['送达时间_dt'].notna(), '配送时长_min']
    station_rows.append({
        '站点': s.replace('分段履约广州', ''),
        '全名': s, '归属': grp,
        '订单量': cnt, '已完成': s_done, '已取消': s_canc,
        '已取货': s_pickup,
        '完成率': round(s_done / cnt * 100, 1) if cnt else 0,
        '编制': staff,
        '人均单量': round(per_person, 1) if per_person else None,
        '距20单缺口': gap,
        '达标': 'Y' if meets else ('N' if staff else '?'),
        '缺口描述': gap_label,
        '平均配送min': round(s_times.mean(), 1) if len(s_times) > 0 else None,
        '中位配送min': round(s_times.median(), 1) if len(s_times) > 0 else None,
        '超60min': int((s_times > 60).sum()),
        '最长配送min': round(s_times.max(), 1) if len(s_times) > 0 else None,
    })

st = pd.DataFrame(station_rows).sort_values('订单量', ascending=False)
st_ours = st[st['归属'] == '我方']
st_comps = st[st['归属'] == '竞争方']

# ════════════════════════════════════════════════════════
# Plotly dark template
# ════════════════════════════════════════════════════════
DARK_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#94a3b8', size=11),
    title=dict(font=dict(color='#e2e8f0', size=13)),
    legend=dict(font=dict(color='#94a3b8')),
    xaxis=dict(gridcolor='rgba(148,163,184,0.08)', linecolor='rgba(148,163,184,0.15)', zeroline=False),
    yaxis=dict(gridcolor='rgba(148,163,184,0.08)', linecolor='rgba(148,163,184,0.15)', zeroline=False),
    dragmode=False,
    margin=dict(t=45, b=60, l=55, r=25),
    hoverlabel=dict(bgcolor='#1e293b', font_size=12, font_family='Inter, sans-serif'),
    bargap=0.18,
)

def dark_fig(fig):
    fig.update_layout(**DARK_LAYOUT)
    return fig

PLOTLY_CONFIG = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d'],
    'scrollZoom': False,
    'doubleClick': False,
    'showTips': False,
    'responsive': True,
    'displaylogo': False,
}

# ════════════════════════════════════════════════════════
# Chart functions
# ════════════════════════════════════════════════════════
def make_hourly_chart(sdf, title='分时订单量', color='#818cf8'):
    hourly = sdf.groupby('hour').size().sort_index()
    if hourly.empty:
        return '<p style="color:#64748b">无数据</p>'
    hour_labels = [f'{h:02d}:00' for h in hourly.index]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hour_labels, y=hourly.values,
        marker_color=color, text=hourly.values, textposition='outside',
        hovertemplate='%{x}<br>%{y}单<extra></extra>'
    ))
    fig.update_layout(title=title, height=260, xaxis_tickangle=-45, yaxis_title=None)
    return dark_fig(fig).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


def make_time_hist(sdf, title='配送时长分布', color='#818cf8'):
    times = sdf.loc[sdf['送达时间_dt'].notna(), '配送时长_min'].dropna()
    if len(times) == 0:
        return '<p style="color:#64748b">无完成订单</p>'
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=times, nbinsx=25, marker_color=color,
        hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
    ))
    for pct, clr, label in [(50, '#34d399', '中位'), (90, '#f87171', 'P90')]:
        val = np.percentile(times, pct)
        fig.add_vline(x=val, line_dash='dash', line_color=clr,
                      annotation_text=f'{label} {val:.0f}min', annotation_position='top')
    fig.update_layout(title=title, height=260, xaxis_title=None, yaxis_title=None, bargap=0.05)
    return dark_fig(fig).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


# ── Overview charts ──
known = st_ours[st_ours['编制'].notna()].copy().sort_values('人均单量')
fig_gap = go.Figure()
fig_gap.add_trace(go.Bar(
    x=known['站点'], y=known['人均单量'],
    marker_color=['#34d399' if v >= 20 else '#f87171' for v in known['人均单量']],
    text=[f'{v:.1f}单/人' for v in known['人均单量']],
    textfont=dict(color='#e2e8f0'),
    textposition='outside', name='人均单量'
))
fig_gap.add_hline(y=20, line_dash='dash', line_color='#fbbf24', line_width=2,
                  annotation_text='门槛: 人均20单', annotation_position='top right',
                  annotation_font_color='#fbbf24')
for _, row in known.iterrows():
    gp = 20 - row['人均单量']
    if gp > 0:
        fig_gap.add_annotation(x=row['站点'], y=row['人均单量'] / 2,
                               text=f'差{gp:.0f}单', showarrow=False,
                               font=dict(color='#fca5a5', size=11))
fig_gap.update_layout(
    title='各点位距「人均20单」补贴门槛',
    height=420, yaxis_title=None,
    yaxis_range=[0, max(known['人均单量'].max() + 5, 25)],
    xaxis_tickangle=-30,
)
html_gap = dark_fig(fig_gap).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_gap')

# Full station bar
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    x=st_ours['站点'], y=st_ours['订单量'],
    marker_color='#818cf8', name=f'我方 ({len(st_ours)}站)',
    text=st_ours['订单量'], textposition='outside',
    textfont=dict(color='#c7d2fe'),
))
fig_bar.add_trace(go.Bar(
    x=st_comps['站点'], y=st_comps['订单量'],
    marker_color='#f87171', name=f'竞争方 ({len(st_comps)}站)',
    text=st_comps['订单量'], textposition='outside',
    textfont=dict(color='#fca5a5'),
))
fig_bar.update_layout(
    title='各站点订单量',
    height=380, xaxis_tickangle=-30, yaxis_title=None,
    legend=dict(orientation='h', yanchor='bottom', y=1.02),
)
html_bar = dark_fig(fig_bar).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_bar')

# All stations hourly
html_hour_all = make_hourly_chart(df, '全站分时订单量', '#818cf8')

# All stations time dist
times_all = df.loc[mask_done, '配送时长_min'].dropna()
fig_time_all = go.Figure()
fig_time_all.add_trace(go.Histogram(
    x=times_all, nbinsx=40, marker_color='#818cf8',
    hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
))
for pct, clr, label in [(50, '#34d399', '中位'), (90, '#f87171', 'P90')]:
    val = np.percentile(times_all, pct)
    fig_time_all.add_vline(x=val, line_dash='dash', line_color=clr,
                           annotation_text=f'{label} {val:.0f}min', annotation_position='top',
                           annotation_font_color=clr)
fig_time_all.update_layout(
    title=f'全站配送时长分布（均值{times_all.mean():.0f}min · n={len(times_all)}）',
    height=320, xaxis_title=None, yaxis_title=None, bargap=0.05,
)
html_time_all = dark_fig(fig_time_all).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_time_all')

# Per-station charts
station_charts = {}
for _, row in st.iterrows():
    full_name = row['全名']
    short = row['站点']
    sdf = df[df['站点名称'] == full_name]
    color = '#818cf8' if row['归属'] == '我方' else '#f87171'
    charts = {}
    charts['hourly'] = make_hourly_chart(sdf, f'{short} · 分时订单量', color)
    charts['time'] = make_time_hist(sdf, f'{short} · 配送时长分布', color)
    station_charts[full_name] = charts

# ════════════════════════════════════════════════════════
# HTML helpers
# ════════════════════════════════════════════════════════
def kpi_card(title, value, sub='', color='#818cf8'):
    return f"""<div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div></div>"""


def build_station_tab(r):
    short = r['站点']
    full_name = r['全名']
    is_ours = r['归属'] == '我方'
    charts = station_charts[full_name]
    staff = int(r['编制']) if pd.notna(r['编制']) else None

    if r['达标'] == 'Y':
        badge = '<span class="badge badge-green">达标</span>'
        status_note = f'人均{r["人均单量"]}单 (+{abs(r["距20单缺口"]):.1f})'
    elif r['达标'] == 'N':
        badge = '<span class="badge badge-red">未达标</span>'
        status_note = f'人均{r["人均单量"]}单 (差{r["距20单缺口"]:.0f}单)'
    else:
        badge = '<span class="badge badge-gray">编制未知</span>'
        status_note = '编制数据缺失'

    # 补贴估算
    subsidy_html = ''
    if is_ours and staff:
        meets_per = r['人均单量'] >= 20 if r['人均单量'] else False
        subsidy_per_day = (staff - 1) * 80 if meets_per else 0
        subsidy_color = '#34d399' if subsidy_per_day > 0 else '#f87171'
        subsidy_html = f"""
        <div class="kpi-card">
            <div class="kpi-title">今日补贴</div>
            <div class="kpi-value" style="color:{subsidy_color}">{subsidy_per_day}元</div>
            <div class="kpi-sub">({staff}-1)x80</div>
        </div>"""

    # 已取货
    pickup_html = ''
    if r['已取货'] > 0:
        pickup_html = kpi_card('配送中(已取货)', r['已取货'], f'截至数据拉取时间', '#fbbf24')

    tab_id = short.replace(' ', '_')
    return f"""
    <div class="tab-panel" id="tab_{tab_id}">
        <div class="kpi-grid">
            {kpi_card('订单量', r['订单量'], f"完成率 {r['完成率']}%", '#818cf8')}
            {kpi_card('已完成', r['已完成'], f"已取消 {r['已取消']}", '#34d399')}
            {pickup_html}
            {kpi_card('编制', f"{staff}人" if staff else "?", '', '#a78bfa')}
            {kpi_card('人均单量', f"{r['人均单量']}单/人" if r['人均单量'] else 'N/A', status_note, '#34d399' if r['达标'] == 'Y' else '#f87171')}
            {subsidy_html}
            {kpi_card('平均配送', f"{r['平均配送min']}min" if pd.notna(r['平均配送min']) else 'N/A', f"中位 {r['中位配送min']}min", '#fbbf24')}
            {kpi_card('超60min', r['超60min'], f"最长 {r['最长配送min']}min" if pd.notna(r['最长配送min']) else '', '#fb923c')}
        </div>

        <div class="note-box">
            <strong>{badge} {short}</strong> | {status_note}
            {'| 补贴条件：人均>=20单 且 >=1人满3h' if is_ours and staff else ''}
        </div>

        <div class="chart-grid">
            <div class="chart-box">{charts['hourly']}</div>
            <div class="chart-box">{charts['time']}</div>
        </div>
    </div>"""


# ════════════════════════════════════════════════════════
# Build tabs
# ════════════════════════════════════════════════════════
tab_buttons = ['<button class="tab-btn active" onclick="switchTab(\'overview\')">总览</button>']

ours_stations = st_ours['全名'].tolist()
for s in ours_stations:
    short = s.replace('分段履约广州', '')
    sid = short.replace(' ', '_')
    tab_buttons.append(f'<button class="tab-btn" onclick="switchTab(\'{sid}\')">{short}</button>')

tab_buttons.append('<span style="margin:0 6px;color:#94A3B8;">|</span>')
for s in st_comps['全名'].tolist():
    short = s.replace('分段履约广州', '')
    sid = short.replace(' ', '_')
    tab_buttons.append(f'<button class="tab-btn tab-comp" onclick="switchTab(\'{sid}\')">{short}</button>')

tab_bar = '\n'.join(tab_buttons)

# ── Overview panel ──
table_html = ''
for _, r in st.iterrows():
    if r['达标'] == 'Y':
        badge = '<span class="badge badge-green">达标</span>'
    elif r['达标'] == 'N':
        badge = '<span class="badge badge-red">未达标</span>'
    else:
        badge = '<span class="badge badge-gray">未知</span>'
    staff_s = f'{int(r["编制"])}人' if pd.notna(r['编制']) else '?'
    per_s = f'{r["人均单量"]}单/人' if pd.notna(r['人均单量']) else 'N/A'
    gap_s = r['缺口描述']
    gap_color = '#f87171' if (r['距20单缺口'] and r['距20单缺口'] > 0) else '#34d399'
    pickup_s = f'· 配送中{r["已取货"]}' if r['已取货'] > 0 else ''
    table_html += f"""
    <tr>
        <td><a href="javascript:switchTab('{r['站点'].replace(' ', '_')}')" style="color:#818cf8;cursor:pointer;text-decoration:underline">{r['站点']}</a></td>
        <td>{r['订单量']}</td>
        <td>{r['完成率']}%</td>
        <td>{staff_s}</td>
        <td>{per_s}</td>
        <td><b style="color:{gap_color}">{gap_s}{pickup_s}</b></td>
        <td>{badge}</td>
        <td>{r['平均配送min']}min</td>
        <td>{r['已取消']}</td>
    </tr>"""

done_pct = done/total*100 if total else 0

tabs_overview = f"""
<div class="tab-panel active" id="tab_overview">
    <div class="note-box" style="border-left-color:#fbbf24;background:rgba(251,191,36,0.08);margin-bottom:14px;">
        <strong>注意：非全天数据</strong> — 时间窗口 {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')}（截至拉取时），
        30单仍在配送中（已取货），完成率等指标为当前快照值。
    </div>

    <div class="kpi-grid">
        {kpi_card('订单总量', total, f'我方 {len(ours)} | 竞争方 {len(comps)}', '#818cf8')}
        {kpi_card('已完成', f'{done_pct:.1f}%', f'{done}已送达 / {canc}取消', '#34d399')}
        {kpi_card('配送中', pickup, '已取货未送达', '#fbbf24')}
        {kpi_card('平均配送时长', f'{avg_time:.0f}min', f'中位 {median_time:.0f}min', '#fbbf24')}
        {kpi_card('峰值', f'{peak_cnt}单', f'{int(peak_h):02d}:00时段', '#f472b6')}
        {kpi_card('超60min', int((df['配送时长_min'] > 60).sum()), f'占比 {(df["配送时长_min"] > 60).sum()/done*100:.1f}%' if done > 0 else '', '#fb923c')}
    </div>

    <div class="section-chart">
        <h2>各点位距「人均20单」补贴门槛</h2>
        {html_gap}
        <div class="note-box">
            <strong>补贴条件</strong>：人均>=20单 <b>且</b> >=1人满3h | 公式：(T-1)x80元/天
            | 3站新增（中大附三岭南医院、汇德国际、云升科技园）编制待确认
        </div>
    </div>

    <div class="section-chart">
        <h2>订单总览（{len(st)}站）</h2>
        {html_bar}
        <div class="chart-grid">
            <div class="chart-box">{html_hour_all}</div>
            <div class="chart-box">{html_time_all}</div>
        </div>
    </div>

    <div class="section-chart">
        <h2>站点明细（点击跳转详页）</h2>
        <div style="max-height:450px;overflow:auto;">
        <table>
            <thead><tr>
                <th>站点</th><th>订单量</th><th>完成率</th><th>编制</th>
                <th>人均单量</th><th>距20单门槛</th><th>达标</th>
                <th>平均配送</th><th>已取消</th>
            </tr></thead>
            <tbody>{table_html}</tbody>
        </table>
        </div>
    </div>
</div>"""

# ── All panels ──
all_panels = [tabs_overview]
for _, r in st.iterrows():
    all_panels.append(build_station_tab(r))

all_panels_html = '\n'.join(all_panels)

# ════════════════════════════════════════════════════════
# Full HTML
# ════════════════════════════════════════════════════════
# Reuse the same CSS from June 17 dashboard
now_str = datetime.now().strftime('%H:%M')
HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · 运营看板 | 2026-06-18</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #06080d;
  --surface: rgba(15, 20, 30, 0.75);
  --surface-hover: rgba(20, 28, 42, 0.85);
  --border: rgba(148, 163, 184, 0.08);
  --border-glow: rgba(129, 140, 248, 0.25);
  --text: #e2e8f0;
  --text-dim: #94a3b8;
  --text-muted: #64748b;
  --accent: #818cf8;
  --accent-glow: rgba(129, 140, 248, 0.35);
  --success: #34d399;
  --success-glow: rgba(52, 211, 153, 0.35);
  --danger: #f87171;
  --danger-glow: rgba(248, 113, 113, 0.35);
  --warning: #fbbf24;
  --warning-glow: rgba(251, 191, 36, 0.3);
  --pink: #f472b6;
  --sky: #38bdf8;
  --radius: 12px;
  --radius-sm: 8px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}}

body::before {{
  content: ''; position: fixed; inset:0; z-index:-1; pointer-events:none;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(129,140,248,0.06) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 80%, rgba(52,211,153,0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 50% 50%, rgba(248,113,113,0.03) 0%, transparent 60%);
}}

.header {{
  position: relative;
  background: linear-gradient(135deg, rgba(15,20,30,0.95), rgba(30,41,59,0.9));
  border-bottom: 1px solid var(--border);
  padding: 22px 32px 14px;
  backdrop-filter: blur(20px);
  overflow: hidden;
}}
.header::after {{
  content: ''; position: absolute; bottom:0; left:0; right:0; height:2px;
  background: linear-gradient(90deg, var(--accent), var(--success), var(--pink), var(--warning));
  opacity: 0.6;
}}
.header h1 {{
  font-size: 24px; font-weight: 800; letter-spacing: -0.5px;
  background: linear-gradient(135deg, #e2e8f0 0%, #818cf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header .meta {{
  font-size: 12px; color: var(--text-dim); margin-top: 4px;
  font-variant-numeric: tabular-nums;
}}

.tab-bar {{
  display:flex; flex-wrap:wrap; gap:3px;
  padding:10px 32px 0;
  background: rgba(10,14,22,0.7);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}}
.tab-btn {{
  padding:7px 16px; border-radius:8px 8px 0 0; border:none; outline:none;
  background:transparent; color:var(--text-dim); cursor:pointer;
  font-size:12.5px; font-weight:500; font-family:inherit;
  transition: all var(--transition);
  position:relative;
}}
.tab-btn::after {{
  content: ''; position:absolute; bottom:0; left:50%; transform:translateX(-50%);
  width:0; height:2px; background:var(--accent);
  border-radius:1px; transition:width var(--transition);
}}
.tab-btn:hover {{ color:#e2e8f0; background:rgba(129,140,248,0.06); }}
.tab-btn:hover::after {{ width:60%; }}
.tab-btn.active {{
  color:#e2e8f0; font-weight:600;
  background:rgba(129,140,248,0.1);
}}
.tab-btn.active::after {{ width:80%; background:var(--accent); box-shadow:0 0 8px var(--accent-glow); }}
.tab-btn.tab-comp {{ color:rgba(248,113,113,0.7); }}
.tab-btn.tab-comp:hover {{ color:#fca5a5; background:rgba(248,113,113,0.06); }}
.tab-btn.tab-comp.active {{ color:#fca5a5; background:rgba(248,113,113,0.1); }}
.tab-btn.tab-comp.active::after {{ background:var(--danger); box-shadow:0 0 8px var(--danger-glow); }}

.container {{ max-width:1340px; margin:0 auto; padding:20px 28px 40px; }}

.tab-panel {{ display:none; animation: fadeSlideIn 0.35s ease; }}
.tab-panel.active {{ display:block; }}
@keyframes fadeSlideIn {{
  from {{ opacity:0; transform:translateY(8px); }}
  to   {{ opacity:1; transform:translateY(0); }}
}}

.kpi-grid {{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(155px,1fr));
  gap:12px; margin-bottom:20px;
}}
.kpi-card {{
  position:relative; overflow:hidden;
  background:var(--surface);
  backdrop-filter: blur(16px);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:16px 18px;
  transition: all var(--transition);
  cursor:default;
}}
.kpi-card:hover {{
  transform:translateY(-2px);
  border-color:var(--border-glow);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px var(--border-glow);
}}
.kpi-card::before {{
  content: ''; position:absolute; top:0; left:0; right:0; height:3px;
  background:var(--accent); opacity:0; transition:opacity var(--transition);
  border-radius:0 0 2px 2px;
}}
.kpi-card:hover::before {{ opacity:1; }}
.kpi-title {{
  font-size:10.5px; color:var(--text-muted); font-weight:600;
  text-transform:uppercase; letter-spacing:0.8px;
}}
.kpi-value {{
  font-size:28px; font-weight:800; margin:3px 0;
  font-variant-numeric:tabular-nums;
  letter-spacing:-1px;
}}
.kpi-sub {{ font-size:11px; color:var(--text-dim); font-weight:400; }}

.section-chart {{
  background:var(--surface);
  backdrop-filter:blur(20px);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px; margin-bottom:16px;
  transition:border-color var(--transition);
}}
.section-chart:hover {{ border-color:rgba(148,163,184,0.15); }}
.section-chart h2 {{
  font-size:15px; font-weight:700; color:var(--text);
  padding-bottom:10px; margin-bottom:14px;
  border-bottom:1px solid var(--border);
  letter-spacing:-0.2px;
  display:flex; align-items:center; gap:8px;
}}
.section-chart h2::before {{
  content: ''; width:4px; height:18px; border-radius:2px;
  background:var(--accent);
}}

.chart-box {{ margin:4px 0; }}
.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}

table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th {{
  background:rgba(30,41,59,0.6); color:var(--text-dim); font-weight:600;
  padding:10px 12px; text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:0.5px;
}}
td {{
  padding:9px 12px; border-bottom:1px solid rgba(148,163,184,0.06);
  color:var(--text);
}}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:rgba(129,140,248,0.04); }}
tr td a {{ color:var(--accent); text-decoration:none; font-weight:500; transition:all .15s; }}
tr td a:hover {{ color:#a5b4fc; text-decoration:underline; }}

.badge {{
  display:inline-block; padding:3px 10px; border-radius:20px;
  font-size:11px; font-weight:600; letter-spacing:0.3px;
}}
.badge-green {{
  background:rgba(52,211,153,0.12); color:#34d399;
  border:1px solid rgba(52,211,153,0.25);
}}
.badge-red {{
  background:rgba(248,113,113,0.12); color:#f87171;
  border:1px solid rgba(248,113,113,0.25);
}}
.badge-gray {{
  background:rgba(148,163,184,0.1); color:#94a3b8;
  border:1px solid rgba(148,163,184,0.2);
}}

.note-box {{
  background:rgba(251,191,36,0.06);
  border:1px solid rgba(251,191,36,0.15);
  border-left:3px solid var(--warning);
  padding:11px 16px; border-radius:var(--radius-sm);
  margin:14px 0; font-size:12px; color:#fcd34d;
}}
.note-box strong {{ color:var(--warning); }}

::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:rgba(148,163,184,0.15); border-radius:3px; }}
::-webkit-scrollbar-thumb:hover {{ background:rgba(148,163,184,0.3); }}

@media (max-width:768px) {{
  .header {{ padding:16px 18px 10px; }}
  .header h1 {{ font-size:20px; }}
  .tab-bar {{ padding:6px 12px 0; gap:2px; }}
  .tab-btn {{ padding:5px 10px; font-size:11px; }}
  .container {{ padding:12px 10px 30px; }}
  .chart-grid {{ grid-template-columns:1fr; }}
  .kpi-grid {{ grid-template-columns:repeat(auto-fit, minmax(130px,1fr)); gap:8px; }}
  .kpi-value {{ font-size:22px; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>接力送 · 运营看板</h1>
    <div class="meta">2026-06-18 &nbsp;·&nbsp; {total}单 &nbsp;·&nbsp; {len(st)}站（我方{len(st_ours)} + 竞争方{len(st_comps)}）&nbsp;·&nbsp; {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')} &nbsp;·&nbsp; {now_str} 更新 &nbsp;·&nbsp; <span style="color:#34d399">近全天数据</span></div>
</div>

<div class="tab-bar">{tab_bar}</div>

<div class="container">
{all_panels_html}
</div>

<script>
function switchTab(tabId) {{
    document.querySelectorAll('.tab-panel').forEach(function(p) {{
        p.classList.remove('active');
    }});
    document.querySelectorAll('.tab-btn').forEach(function(b) {{
        b.classList.remove('active');
    }});
    var panel = document.getElementById('tab_' + tabId);
    if (panel) {{
        panel.classList.add('active');
        panel.querySelectorAll('.js-plotly-plot').forEach(function(el) {{
            if (el._plotly) Plotly.Plots.resize(el);
        }});
    }}
    var btns = document.querySelectorAll('.tab-btn');
    btns.forEach(function(b) {{
        var oc = b.getAttribute('onclick') || '';
        if (oc.indexOf("'" + tabId + "'") !== -1) b.classList.add('active');
    }});
    window.scrollTo({{top:0, behavior:'smooth'}});
}}
</script>

</body>
</html>"""

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(HTML)
with open(INDEX_OUT, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f'[OK] {OUTPUT}')
print(f'[OK] {INDEX_OUT}')
print(f'     {total} orders | {len(st)} stations | ours={len(st_ours)} comp={len(st_comps)}')
print(f'     Time: {t_min.strftime("%H:%M")} - {t_max.strftime("%H:%M")} (partial day)')
print(f'     Done={done}  Cancelled={canc}  Pickup={pickup}')
print(f'     Tabs: 1 overview + {len(st)} station details')
