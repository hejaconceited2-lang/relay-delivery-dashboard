"""
接力送 · 运营看板（多Tab版）
总览 + 每点位独立分页
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ── 加载 & 过滤 ─────────────────────────────────────────────
INPUT = r"D:\CC\接力送日订单\26-06-17\[新]校园订单详情_20260617_213418_5.xls"
OUTPUT = r"D:\CC\接力送日订单\26-06-17\operations_dashboard.html"
INDEX_OUT = r"D:\CC\接力送日订单\26-06-17\index.html"

df = pd.read_excel(INPUT)
df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

# ── 预处理 ───────────────────────────────────────────────────
df['下单时间_dt'] = pd.to_datetime(df['下单时间'], errors='coerce')
df['送达时间_dt'] = pd.to_datetime(df['送达时间'], errors='coerce')
df['hour'] = df['下单时间_dt'].dt.hour
mask_done = df['送达时间_dt'].notna()
df.loc[mask_done, '配送时长_min'] = (
    df.loc[mask_done, '送达时间_dt'] - df.loc[mask_done, '下单时间_dt']
).dt.total_seconds() / 60

rider_cols = ['经手骑手1', '经手骑手2', '经手骑手3', '经手骑手4', '经手骑手5']
df['rider_count'] = df[rider_cols].notna().sum(axis=1)

# ── 分类 ─────────────────────────────────────────────────────
COMPETITORS = {'分段履约广州新中国大厦', '分段履约广州新亚洲电子城', '分段履约广州孙逸仙北院'}
df['归属'] = df['站点名称'].apply(lambda s: '竞争方' if s in COMPETITORS else '我方')

KNOWN_STAFF = {
    '分段履约广州绿地星玥': 5, '分段履约广州万菱广场': 2,
    '分段履约广州和业广场': 3, '分段履约广州金鹰大厦': 2,
    '分段履约广州华林国际C馆': 2, '分段履约广州中大附属第六医院': 2,
    '分段履约广州珠江国际轻纺城': 3, '分段履约广州万科欧泊': 3,
    '分段履约广州孙逸仙北院': 2, '分段履约广州新亚洲电子城': 3,
    '分段履约广州新中国大厦': 3,
}

# ── 全局汇总 ─────────────────────────────────────────────────
total = len(df)
ours = df[df['归属'] == '我方']
comps = df[df['归属'] == '竞争方']
done = (df['物流单状态'] == '已送达').sum()
canc = (df['物流单状态'] == '已取消').sum()
avg_time = df.loc[mask_done, '配送时长_min'].mean()
median_time = df.loc[mask_done, '配送时长_min'].median()
peak_h = df['hour'].value_counts().idxmax()
peak_cnt = df['hour'].value_counts().max()

# ── 站点汇总 ─────────────────────────────────────────────────
station_rows = []
for s in df['站点名称'].unique():
    sdf = df[df['站点名称'] == s]
    cnt = len(sdf)
    s_done = (sdf['物流单状态'] == '已送达').sum()
    s_canc = (sdf['物流单状态'] == '已取消').sum()
    grp = sdf['归属'].iloc[0]
    staff = KNOWN_STAFF.get(s)
    per_person = cnt / staff if staff else None

    if staff and per_person:
        gap = 20 - per_person
        gap_pct = round(per_person / 20 * 100, 1)
        gap_label = f'还差 {gap:.0f} 单 ({gap_pct:.0f}%)' if gap > 0 else f'达标 ✓ (+{-gap:.0f}单)'
        meets = per_person >= 20
    else:
        gap = None; gap_pct = None; gap_label = '编制未知'; meets = False

    s_times = sdf.loc[sdf['送达时间_dt'].notna(), '配送时长_min']
    station_rows.append({
        '站点': s.replace('分段履约广州', ''),
        '全名': s, '归属': grp,
        '订单量': cnt, '已完成': s_done, '已取消': s_canc,
        '完成率': round(s_done / cnt * 100, 1) if cnt else 0,
        '编制': staff,
        '人均单量': round(per_person, 1) if per_person else None,
        '距20单缺口': gap, '距20单%': gap_pct,
        '达标': '✓' if meets else ('✗' if staff else '?'),
        '缺口描述': gap_label,
        '平均配送min': round(s_times.mean(), 1) if len(s_times) > 0 else None,
        '中位配送min': round(s_times.median(), 1) if len(s_times) > 0 else None,
        '超60min': int((s_times > 60).sum()),
        '最长配送min': round(s_times.max(), 1) if len(s_times) > 0 else None,
    })

st = pd.DataFrame(station_rows).sort_values('订单量', ascending=False)
st_ours = st[st['归属'] == '我方']
st_comps = st[st['归属'] == '竞争方']


# ══════════════════════════════════════════════════════════════
# 图表生成函数
# ══════════════════════════════════════════════════════════════

def make_hourly_chart(sdf, title='分时订单量', color='#6366F1'):
    hourly = sdf.groupby('hour').size().sort_index()
    if hourly.empty:
        return '<p style="color:#94A3B8">无数据</p>'
    hour_labels = [f'{h:02d}:00-{h:02d}:59' for h in hourly.index]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hour_labels, y=hourly.values,
        marker_color=color, text=hourly.values, textposition='outside',
        hovertemplate='%{x}<br>%{y}单<extra></extra>'
    ))
    fig.update_layout(
        title=title, height=260, margin=dict(t=40, b=50, l=50, r=20),
        xaxis_tickangle=-45, yaxis_title='单',
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def make_time_hist(sdf, title='配送时长分布', color='#6366F1'):
    times = sdf.loc[sdf['送达时间_dt'].notna(), '配送时长_min'].dropna()
    if len(times) == 0:
        return '<p style="color:#94A3B8">无完成订单</p>'
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=times, nbinsx=25, marker_color=color,
        hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
    ))
    for pct, clr, label in [(50, '#22C55E', '中位'), (90, '#EF4444', 'P90')]:
        val = np.percentile(times, pct)
        fig.add_vline(x=val, line_dash='dash', line_color=clr,
                      annotation_text=f'{label} {val:.0f}min', annotation_position='top')
    fig.update_layout(
        title=title, height=260, margin=dict(t=40, b=50, l=50, r=20),
        xaxis_title='分钟', yaxis_title='单', bargap=0.05,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


# ── 总览图表 ─────────────────────────────────────────────────
# 图表1: 人均单量距20单门槛
known = st_ours[st_ours['编制'].notna()].copy().sort_values('人均单量')
fig_gap = go.Figure()
fig_gap.add_trace(go.Bar(
    x=known['站点'], y=known['人均单量'],
    marker_color=['#22C55E' if v >= 20 else '#EF4444' for v in known['人均单量']],
    text=[f'{v:.1f}单/人' for v in known['人均单量']],
    textposition='outside', name='人均单量'
))
fig_gap.add_hline(y=20, line_dash='dash', line_color='#F59E0B', line_width=2,
                  annotation_text='门槛: 人均20单', annotation_position='top right')
for _, row in known.iterrows():
    gp = 20 - row['人均单量']
    if gp > 0:
        fig_gap.add_annotation(x=row['站点'], y=row['人均单量'] / 2,
                               text=f'差{gp:.0f}单', showarrow=False,
                               font=dict(color='#991B1B', size=11))
fig_gap.update_layout(
    title='<b>各点位距「人均20单」补贴门槛</b>',
    height=420, yaxis_title='人均单量',
    yaxis_range=[0, max(known['人均单量'].max() + 5, 25)],
    margin=dict(t=60, b=80), xaxis_tickangle=-30,
)
html_gap = fig_gap.to_html(full_html=False, include_plotlyjs=False, div_id='chart_gap')

# 图表2: 全站点订单量
fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    x=st_ours['站点'], y=st_ours['订单量'],
    marker_color='#6366F1', name=f'我方 ({len(st_ours)}站)',
    text=st_ours['订单量'], textposition='outside',
))
fig_bar.add_trace(go.Bar(
    x=st_comps['站点'], y=st_comps['订单量'],
    marker_color='#EF4444', name=f'竞争方 ({len(st_comps)}站)',
    text=st_comps['订单量'], textposition='outside',
))
fig_bar.update_layout(
    title='各站点订单量',
    height=380, xaxis_tickangle=-30, yaxis_title='订单数',
    legend=dict(orientation='h', yanchor='bottom', y=1.02),
    margin=dict(t=50, b=100),
)
html_bar = fig_bar.to_html(full_html=False, include_plotlyjs=False, div_id='chart_bar')

# 图表3: 全站分时
html_hour_all = make_hourly_chart(df, '全站分时订单量')

# 图表4: 全站配送时长
times_all = df.loc[mask_done, '配送时长_min'].dropna()
fig_time_all = go.Figure()
fig_time_all.add_trace(go.Histogram(
    x=times_all, nbinsx=40, marker_color='#6366F1',
    hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
))
for pct, clr, label in [(50, '#22C55E', '中位'), (90, '#EF4444', 'P90')]:
    val = np.percentile(times_all, pct)
    fig_time_all.add_vline(x=val, line_dash='dash', line_color=clr,
                           annotation_text=f'{label} {val:.0f}min', annotation_position='top')
fig_time_all.update_layout(
    title=f'全站配送时长分布（均值{times_all.mean():.0f}min · n={len(times_all)}）',
    height=320, xaxis_title='分钟', yaxis_title='订单数', bargap=0.05,
)
html_time_all = fig_time_all.to_html(full_html=False, include_plotlyjs=False, div_id='chart_time_all')

# ── 每个站点明细图表 ──────────────────────────────────────────
station_charts = {}
for _, row in st.iterrows():
    full_name = row['全名']
    short = row['站点']
    sdf = df[df['站点名称'] == full_name]
    is_ours = row['归属'] == '我方'
    color = '#6366F1' if is_ours else '#EF4444'

    charts = {}
    charts['hourly'] = make_hourly_chart(sdf, f'{short} · 分时订单量', color)
    charts['time']   = make_time_hist(sdf, f'{short} · 配送时长分布', color)
    station_charts[full_name] = charts


# ══════════════════════════════════════════════════════════════
# HTML 渲染
# ══════════════════════════════════════════════════════════════

def kpi_card(title, value, sub='', color='#6366F1'):
    return f"""<div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div></div>"""


def make_assessment(r):
    """生成站点运营简要评估"""
    short = r['站点']
    is_ours = r['归属'] == '我方'
    staff = int(r['编制']) if pd.notna(r['编制']) else None
    per = r['人均单量']
    orders = r['订单量']
    comp_rate = r['完成率']
    over60 = r['超60min']

    lines = []

    if staff and per is not None:
        # ── 人均达标评估 ──
        if per >= 20:
            if per >= 25:
                lines.append(f'人均{per:.1f}单，大幅超出门槛，人员配置紧张，产能利用率高')
            elif per >= 22:
                lines.append(f'人均{per:.1f}单，超出门槛，人员配置与单量匹配良好')
            else:
                lines.append(f'人均{per:.1f}单，恰好达标，缓冲空间有限，单量波动可能导致滑出达标线')
        else:
            gap = 20 - per
            if gap <= 1:
                lines.append(f'人均{per:.1f}单，距门槛仅差{gap:.1f}单，自然波动即可达标，暂无需调整')
            elif gap <= 3:
                lines.append(f'人均{per:.1f}单，距门槛差{gap:.0f}单，建议观察多日趋势后再决定是否缩减1人')
            elif gap <= 6:
                lines.append(f'人均{per:.1f}单，距门槛差{gap:.0f}单，建议缩减1人或提升单量')
            else:
                lines.append(f'人均{per:.1f}单，距门槛差{gap:.0f}单，人员严重超配，强烈建议缩减编制')

        # ── 产能匹配度（12单/h基准） ──
        if staff:
            capacity = staff * 3 * 12  # 假设每人3h峰值
            utilization = orders / capacity * 100 if capacity > 0 else 0
            needed_staff_3h = max(1, __import__('math').ceil(orders / (3 * 12)))
            if needed_staff_3h < staff and per < 20:
                lines.append(f'按12单/h/人×3h计，{orders}单仅需{needed_staff_3h}人，当前{staff}人超配{staff-needed_staff_3h}人')

        # ── 配送质量 ──
        if over60 > orders * 0.1:
            lines.append(f'超60min订单{over60}单（{over60/orders*100:.0f}%），配送时效偏长，需关注')
        elif comp_rate < 90:
            lines.append(f'完成率仅{comp_rate:.1f}%，取消率偏高，需排查原因')

        # ── 补贴评估（仅我方） ──
        if is_ours:
            if per >= 20:
                subsidy = (staff - 1) * 80
                lines.append(f'可获补贴{subsidy}元/天（({staff}-1)×80），人均{orders/staff:.1f}单满足条件')
            else:
                lines.append('当前未达补贴条件，人均≥20单且≥1人满3h才可触发')

    elif staff is None:
        lines.append('编制数据缺失，无法评估')

    if not lines:
        return ''

    items = '\n'.join([f'<li>{l}</li>' for l in lines])
    return f"""
    <div class="section-chart" style="margin-bottom:10px;">
        <h2>📝 {short} · 运营评估</h2>
        <ul style="font-size:13px;line-height:1.8;padding-left:20px;color:#475569;">
            {items}
        </ul>
    </div>"""


def build_station_tab(r):
    """生成单个站点的Tab内容"""
    short = r['站点']
    full_name = r['全名']
    is_ours = r['归属'] == '我方'
    charts = station_charts[full_name]
    staff = int(r['编制']) if pd.notna(r['编制']) else None

    # 状态徽章
    if r['达标'] == '✓':
        badge = '<span class="badge badge-green">达标</span>'
        status_note = f'人均{r["人均单量"]}单，超出门槛{abs(r["距20单缺口"]):.1f}单'
    elif r['达标'] == '✗':
        badge = '<span class="badge badge-red">未达标</span>'
        status_note = f'人均{r["人均单量"]}单，距门槛还差{r["距20单缺口"]:.0f}单'
    else:
        badge = '<span class="badge badge-gray">编制未知</span>'
        status_note = '编制数据缺失，无法计算人均单量'

    # 补贴估算（仅我方有编制站点）
    subsidy_html = ''
    if is_ours and staff:
        meets_per = r['人均单量'] >= 20 if r['人均单量'] else False
        subsidy_per_day = (staff - 1) * 80 if meets_per else 0
        subsidy_color = '#22C55E' if subsidy_per_day > 0 else '#EF4444'
        subsidy_html = f"""
        <div class="kpi-card">
            <div class="kpi-title">今日补贴</div>
            <div class="kpi-value" style="color:{subsidy_color}">{subsidy_per_day}元</div>
            <div class="kpi-sub">公式: ({staff}-1)×80</div>
        </div>"""

    tab_id = short.replace(' ', '_')
    assessment = make_assessment(r)

    return f"""
    <div class="tab-panel" id="tab_{tab_id}">
        <div class="kpi-grid">
            {kpi_card('订单量', r['订单量'], f"完成率 {r['完成率']}%", '#6366F1')}
            {kpi_card('已完成', r['已完成'], f"已取消 {r['已取消']}", '#22C55E')}
            {kpi_card('编制', f"{staff}人" if staff else "?", '', '#8B5CF6')}
            {kpi_card('人均单量', f"{r['人均单量']}单/人" if r['人均单量'] else 'N/A', status_note, '#22C55E' if r['达标'] == '✓' else '#EF4444')}
            {subsidy_html}
            {kpi_card('平均配送', f"{r['平均配送min']}min" if pd.notna(r['平均配送min']) else 'N/A', f"中位 {r['中位配送min']}min", '#F59E0B')}
            {kpi_card('超60min', r['超60min'], f"最长 {r['最长配送min']}min" if pd.notna(r['最长配送min']) else '', '#F97316')}
        </div>

        <div class="note-box" style="margin-bottom:12px;">
            <strong>{badge} {short}</strong> | {status_note}
            {'| 补贴条件：人均≥20单 且 ≥1人满3h | 公式：(T-1)×80元/天' if is_ours and staff else ''}
        </div>

        {assessment}

        <div class="chart-grid">
            <div class="chart-box">{charts['hourly']}</div>
            <div class="chart-box">{charts['time']}</div>
        </div>
    </div>"""


# ── 生成所有Tab面板 ─────────────────────────────────────────
tabs_overview = '<div class="tab-panel active" id="tab_overview">'

# Tabs列表
tab_buttons = ['<button class="tab-btn active" onclick="switchTab(\'overview\')">📊 总览</button>']

# 我方站点tabs
ours_stations = st_ours['全名'].tolist()
for s in ours_stations:
    short = s.replace('分段履约广州', '')
    sid = short.replace(' ', '_')
    tab_buttons.append(f'<button class="tab-btn" onclick="switchTab(\'{sid}\')">{short}</button>')

# 竞争方站点tabs
tab_buttons.append('<span style="margin:0 6px;color:#94A3B8;">|</span>')
for s in st_comps['全名'].tolist():
    short = s.replace('分段履约广州', '')
    sid = short.replace(' ', '_')
    tab_buttons.append(f'<button class="tab-btn tab-comp" onclick="switchTab(\'{sid}\')">🔴 {short}</button>')

tab_bar = '\n'.join(tab_buttons)

# ── 总览面板 ─────────────────────────────────────────────────
# 站点明细表
table_html = ''
for _, r in st.iterrows():
    if r['达标'] == '✓':
        badge = '<span class="badge badge-green">达标</span>'
    elif r['达标'] == '✗':
        badge = '<span class="badge badge-red">未达标</span>'
    else:
        badge = '<span class="badge badge-gray">未知</span>'
    staff_s = f'{int(r["编制"])}人' if pd.notna(r['编制']) else '?'
    per_s = f'{r["人均单量"]}单/人' if pd.notna(r['人均单量']) else 'N/A'
    gap_s = r['缺口描述']
    gap_color = '#EF4444' if (r['距20单缺口'] and r['距20单缺口'] > 0) else '#22C55E'
    table_html += f"""
    <tr>
        <td><a href="javascript:switchTab('{r['站点'].replace(' ', '_')}')" style="color:#6366F1;cursor:pointer;text-decoration:underline">{r['站点']}</a></td>
        <td>{r['订单量']}</td>
        <td>{r['完成率']}%</td>
        <td>{staff_s}</td>
        <td>{per_s}</td>
        <td><b style="color:{gap_color}">{gap_s}</b></td>
        <td>{badge}</td>
        <td>{r['平均配送min']}min</td>
        <td>{r['已取消']}</td>
    </tr>"""

tabs_overview += f"""
    <div class="kpi-grid">
        {kpi_card('订单总量', total, f'我方 {len(ours)} | 竞争方 {len(comps)}', '#6366F1')}
        {kpi_card('完成率', f'{done/total*100:.1f}%', f'{done}已送达 / {canc}取消', '#22C55E')}
        {kpi_card('平均配送时长', f'{avg_time:.0f}min', f'中位 {median_time:.0f}min', '#F59E0B')}
        {kpi_card('午峰峰值', peak_cnt, f'{peak_h:02d}:00-{peak_h:02d}:59', '#EC4899')}
        {kpi_card('超60min订单', int((df['配送时长_min'] > 60).sum()), f'占比 {(df["配送时长_min"] > 60).sum()/done*100:.1f}%', '#F97316')}
    </div>

    <div class="section-chart">
        <h2>🎯 各点位距「人均20单」补贴门槛</h2>
        {html_gap}
        <div class="note-box">
            <strong>补贴条件</strong>：人均≥20单 <b>且</b> 至少1人满3h | 公式：(T-1)×80元/天
            | 8站中 <b>3站达标</b>（中大附属第六医院31.0、绿地星玥24.6、和业广场20.7）
        </div>
    </div>

    <div class="section-chart">
        <h2>📊 订单总览</h2>
        {html_bar}
        <div class="chart-grid">
            <div class="chart-box">{html_hour_all}</div>
            <div class="chart-box">{html_time_all}</div>
        </div>
    </div>

    <div class="section-chart">
        <h2>📋 站点明细（点击站点名跳转详情页）</h2>
        <div style="max-height:400px;overflow:auto;">
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

# ── 各站点面板 ──────────────────────────────────────────────
all_panels = [tabs_overview]
for _, r in st.iterrows():
    all_panels.append(build_station_tab(r))

all_panels_html = '\n'.join(all_panels)

# ── 完整HTML ─────────────────────────────────────────────────
HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · 运营看板 | 2026-06-17</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#F1F5F9; color:#1E293B; }}
.header {{ background:linear-gradient(135deg, #1E293B 0%, #334155 100%); color:#fff; padding:18px 28px 12px; }}
.header h1 {{ font-size:22px; margin-bottom:2px; }}
.header .meta {{ font-size:12px; opacity:0.7; margin-bottom:10px; }}

/* ── Tabs ── */
.tab-bar {{
    display:flex; flex-wrap:wrap; gap:4px; padding:8px 28px 0;
    background:#1E293B;
}}
.tab-btn {{
    padding:6px 14px; border-radius:6px 6px 0 0; border:none;
    background:#334155; color:#94A3B8; cursor:pointer;
    font-size:13px; transition:background .15s;
}}
.tab-btn:hover {{ background:#475569; color:#E2E8F0; }}
.tab-btn.active {{ background:#F1F5F9; color:#1E293B; font-weight:600; }}
.tab-btn.tab-comp.active {{ background:#FEF2F2; color:#991B1B; }}

.container {{ max-width:1200px; margin:0 auto; padding:16px 24px; }}
.tab-panel {{ display:none; }}
.tab-panel.active {{ display:block; }}

/* ── KPI ── */
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(150px,1fr)); gap:10px; margin-bottom:16px; }}
.kpi-card {{ background:#fff; border-radius:8px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.kpi-title {{ font-size:11px; color:#64748B; text-transform:uppercase; }}
.kpi-value {{ font-size:24px; font-weight:700; margin:2px 0; }}
.kpi-sub {{ font-size:11px; color:#94A3B8; }}

/* ── section / chart ── */
.section-chart {{ background:#fff; border-radius:10px; padding:18px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
.section-chart h2 {{ font-size:16px; border-bottom:2px solid #6366F1; padding-bottom:6px; margin-bottom:12px; }}
.chart-box {{ margin:8px 0; }}
.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}

/* ── table ── */
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #E2E8F0; }}
th {{ background:#F8FAFC; color:#475569; font-weight:600; }}
tr:hover {{ background:#F1F5F9; }}

/* ── badges ── */
.badge {{ padding:2px 8px; border-radius:10px; font-size:12px; color:#fff; }}
.badge-green {{ background:#22C55E; }}
.badge-red {{ background:#EF4444; }}
.badge-gray {{ background:#9CA3AF; }}

.note-box {{ background:#FEF3C7; border-left:4px solid #F59E0B; padding:10px 14px; border-radius:6px; margin:12px 0; font-size:12px; }}
.note-box strong {{ color:#B45309; }}

@media (max-width:768px) {{
    .chart-grid {{ grid-template-columns:1fr; }}
    .kpi-grid {{ grid-template-columns:repeat(auto-fit, minmax(120px,1fr)); }}
    .tab-bar {{ padding:6px 12px 0; gap:2px; }}
    .tab-btn {{ padding:4px 8px; font-size:11px; }}
    .container {{ padding:10px 8px; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>接力送 · 运营看板</h1>
    <div class="meta">2026-06-17 | {total}单 | 11站（我方8 + 竞争方3）| 07:54-19:09 | {datetime.now().strftime('%H:%M')} 更新</div>
</div>

<div class="tab-bar">{tab_bar}</div>

<div class="container">
{all_panels_html}
</div>

<script>
function switchTab(tabId) {{
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    var panel = document.getElementById('tab_' + tabId);
    if (panel) panel.classList.add('active');
    var btns = document.querySelectorAll('.tab-btn');
    btns.forEach(function(b) {{
        var onclick = b.getAttribute('onclick') || '';
        if (onclick.indexOf("'" + tabId + "'") !== -1 || onclick.indexOf('"' + tabId + '"') !== -1) {{
            b.classList.add('active');
        }}
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
print(f'     Tabs: 1 总览 + {len(st)} 站点详页')
