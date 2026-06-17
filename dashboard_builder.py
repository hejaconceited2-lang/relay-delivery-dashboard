"""
接力送 · 运营看板（精简版）
聚焦：各点位距人均20单补贴目标的差距
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ── 加载 & 过滤 ─────────────────────────────────────────────
INPUT = r"D:\CC\接力送日订单\26-06-17\[新]校园订单详情_20260617_155603_6.xls"
OUTPUT = r"D:\CC\接力送日订单\26-06-17\operations_dashboard.html"

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
    '分段履约广州华林国际C馆': 2,
}

# ── 汇总 ─────────────────────────────────────────────────────
total = len(df)
ours = df[df['归属'] == '我方']
comps = df[df['归属'] == '竞争方']
done = (df['物流单状态'] == '已送达').sum()
canc = (df['物流单状态'] == '已取消').sum()
avg_time = df.loc[mask_done, '配送时长_min'].mean()
median_time = df.loc[mask_done, '配送时长_min'].median()
peak_h = df['hour'].value_counts().idxmax()
peak_cnt = df['hour'].value_counts().max()

# ── 站点汇总（核心：人均单量 vs 20单门槛） ──────────────────
station_rows = []
for s in df['站点名称'].unique():
    sdf = df[df['站点名称'] == s]
    cnt = len(sdf)
    s_done = (sdf['物流单状态'] == '已送达').sum()
    s_canc = (sdf['物流单状态'] == '已取消').sum()
    grp = sdf['归属'].iloc[0]
    staff = KNOWN_STAFF.get(s)
    per_person = cnt / staff if staff else None

    # 距20单门槛的缺口
    if staff and per_person:
        gap = 20 - per_person  # 正数=还差多少, 负数=超出
        gap_pct = round(per_person / 20 * 100, 1)
        gap_label = f'还差 {gap:.0f} 单 ({gap_pct:.0f}%)' if gap > 0 else f'达标 ✓ (+{-gap:.0f}单)'
        meets = per_person >= 20
    else:
        gap = None
        gap_pct = None
        gap_label = '编制未知'
        meets = False

    s_times = sdf.loc[sdf['送达时间_dt'].notna(), '配送时长_min']
    station_rows.append({
        '站点': s.replace('分段履约广州', ''),
        '全名': s,
        '归属': grp,
        '订单量': cnt,
        '已完成': s_done,
        '已取消': s_canc,
        '完成率': round(s_done / cnt * 100, 1) if cnt else 0,
        '编制': staff,
        '人均单量': round(per_person, 1) if per_person else None,
        '距20单缺口': gap,
        '距20单%': gap_pct,
        '达标': '✓' if meets else ('✗' if staff else '?'),
        '缺口描述': gap_label,
        '平均配送min': round(s_times.mean(), 1) if len(s_times) > 0 else None,
        '超60min': int((s_times > 60).sum()),
    })

st = pd.DataFrame(station_rows).sort_values('订单量', ascending=False)
st_ours = st[st['归属'] == '我方']
st_comps = st[st['归属'] == '竞争方']

# ── 图表1: 人均单量距20单门槛 — 核心图 ──────────────────────
fig_gap = go.Figure()

# 只对我方有编制站点画图
known = st_ours[st_ours['编制'].notna()].copy()
known = known.sort_values('人均单量')

fig_gap.add_trace(go.Bar(
    x=known['站点'],
    y=known['人均单量'],
    marker_color=['#22C55E' if v >= 20 else '#EF4444' for v in known['人均单量']],
    text=[f'{v:.1f}单/人' for v in known['人均单量']],
    textposition='outside',
    name='人均单量'
))
# 20单门槛线
fig_gap.add_hline(y=20, line_dash='dash', line_color='#F59E0B', line_width=2,
                  annotation_text='补贴门槛: 人均20单', annotation_position='top right')
# 缺口标注
for _, row in known.iterrows():
    gap = 20 - row['人均单量']
    if gap > 0:
        fig_gap.add_annotation(
            x=row['站点'], y=row['人均单量'] / 2,
            text=f'差{gap:.0f}单',
            showarrow=False, font=dict(color='#991B1B', size=11)
        )

fig_gap.update_layout(
    title='<b>核心指标：各点位距「人均20单」补贴门槛差距</b><br><sub>仅有编制的5个我方站点可计算 · 编制数据来自UE模型参数</sub>',
    height=420,
    yaxis_title='人均单量',
    yaxis_range=[0, max(known['人均单量'].max() + 5, 25)],
    margin=dict(t=80, b=80),
    xaxis_tickangle=-30,
)

# ── 图表2: 全站点订单量总览 ──────────────────────────────────
fig_bar = go.Figure()
# 我方
fig_bar.add_trace(go.Bar(
    x=st_ours['站点'], y=st_ours['订单量'],
    marker_color='#6366F1', name=f'我方 ({len(st_ours)}站)',
    text=st_ours['订单量'], textposition='outside',
))
# 竞争方
fig_bar.add_trace(go.Bar(
    x=st_comps['站点'], y=st_comps['订单量'],
    marker_color='#EF4444', name=f'竞争方 ({len(st_comps)}站)',
    text=st_comps['订单量'], textposition='outside',
))
fig_bar.update_layout(
    title='各站点订单量（蓝=我方 · 红=竞争方）',
    height=380, xaxis_tickangle=-30,
    yaxis_title='订单数',
    legend=dict(orientation='h', yanchor='bottom', y=1.02),
    margin=dict(t=50, b=100),
)

# ── 图表3: 分时订单分布 ──────────────────────────────────────
hourly = df.groupby('hour').size().sort_index()
hour_labels = [f'{h:02d}:00-{h:02d}:59' for h in hourly.index]
fig_hour = go.Figure()
fig_hour.add_trace(go.Bar(
    x=hour_labels, y=hourly.values,
    marker_color='#6366F1', text=hourly.values, textposition='outside',
    hovertemplate='%{x}<br>%{y}单<extra></extra>'
))
fig_hour.update_layout(
    title='分时订单量',
    height=320, xaxis_tickangle=-45,
    yaxis_title='订单数', xaxis_title='时间段',
)

# ── 图表4: 配送时长分布 ─────────────────────────────────────
times = df.loc[mask_done, '配送时长_min'].dropna()
fig_time = go.Figure()
fig_time.add_trace(go.Histogram(
    x=times, nbinsx=40, marker_color='#6366F1',
    hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
))
for pct, color, label in [(50, '#22C55E', '中位'), (90, '#EF4444', 'P90')]:
    val = np.percentile(times, pct)
    fig_time.add_vline(x=val, line_dash='dash', line_color=color,
                       annotation_text=f'{label} {val:.0f}min', annotation_position='top')
fig_time.update_layout(
    title=f'配送时长分布（均值{times.mean():.0f}min · n={len(times)}）',
    height=320, xaxis_title='分钟', yaxis_title='订单数', bargap=0.05
)

# ── 图表5: 竞争方子项 ────────────────────────────────────────
fig_comp = go.Figure()
fig_comp.add_trace(go.Bar(
    x=st_comps['站点'], y=st_comps['订单量'],
    marker_color='#EF4444',
    text=st_comps.apply(lambda r: f"{r['订单量']}单 | 完成率{r['完成率']}%", axis=1),
    textposition='outside',
))
fig_comp.update_layout(
    title='竞争方站点 · 订单量 & 完成率',
    height=300, xaxis_tickangle=-30,
    yaxis_title='订单数',
    margin=dict(t=50, b=80),
)

# ── 站点明细表（精简） ───────────────────────────────────────
table_html = ''
for _, r in st.iterrows():
    if r['达标'] == '✓':
        badge = '<span style="background:#22C55E;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">达标</span>'
    elif r['达标'] == '✗':
        badge = '<span style="background:#EF4444;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">未达标</span>'
    else:
        badge = '<span style="background:#9CA3AF;color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">未知</span>'

    staff_s = f'{int(r["编制"])}人' if pd.notna(r['编制']) else '?'
    per_s = f'{r["人均单量"]}单/人' if pd.notna(r['人均单量']) else 'N/A'
    gap_s = r['缺口描述']
    gap_color = '#EF4444' if (r['距20单缺口'] and r['距20单缺口'] > 0) else '#22C55E'

    table_html += f"""
    <tr>
        <td>{r['站点']}</td>
        <td>{r['订单量']}</td>
        <td>{r['完成率']}%</td>
        <td>{staff_s}</td>
        <td>{per_s}</td>
        <td><b style="color:{gap_color}">{gap_s}</b></td>
        <td>{badge}</td>
        <td>{r['平均配送min']}min</td>
        <td>{r['已取消']}</td>
    </tr>"""

# ── HTML ─────────────────────────────────────────────────────
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
.header {{ background:linear-gradient(135deg, #1E293B 0%, #334155 100%); color:#fff; padding:18px 28px; }}
.header h1 {{ font-size:22px; margin-bottom:2px; }}
.header .meta {{ font-size:12px; opacity:0.7; }}
.container {{ max-width:1100px; margin:0 auto; padding:16px; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px,1fr)); gap:10px; margin-bottom:16px; }}
.kpi-card {{ background:#fff; border-radius:8px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,.06); }}
.kpi-title {{ font-size:11px; color:#64748B; text-transform:uppercase; }}
.kpi-value {{ font-size:24px; font-weight:700; margin:2px 0; }}
.kpi-sub {{ font-size:11px; color:#94A3B8; }}
.section {{ background:#fff; border-radius:10px; padding:18px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
.section h2 {{ font-size:16px; border-bottom:2px solid #6366F1; padding-bottom:6px; margin-bottom:12px; }}
.section-sub {{ background:#FEF2F2; border-radius:10px; padding:18px; margin-bottom:14px; border:1px solid #FECACA; }}
.section-sub h2 {{ font-size:16px; border-bottom:2px solid #EF4444; padding-bottom:6px; margin-bottom:12px; color:#991B1B; }}
.chart-box {{ margin:8px 0; }}
.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid #E2E8F0; }}
th {{ background:#F8FAFC; color:#475569; font-weight:600; }}
tr:hover {{ background:#F1F5F9; }}
.note-box {{ background:#FEF3C7; border-left:4px solid #F59E0B; padding:10px 14px; border-radius:6px; margin:12px 0; font-size:12px; }}
.note-box strong {{ color:#B45309; }}
.mini-metrics {{ display:flex; flex-wrap:wrap; gap:8px; margin:8px 0; }}
.mini-kpi {{ background:#fff; border-radius:6px; padding:8px 12px; text-align:center; font-size:12px; min-width:80px; box-shadow:0 1px 2px rgba(0,0,0,.03); }}
.mini-kpi b {{ display:block; color:#6366F1; font-size:10px; }}
</style>
</head>
<body>

<div class="header">
    <h1>接力送 · 运营看板</h1>
    <div class="meta">2026-06-17 | {total}单 | 10站（我方7 + 竞争方3）| {datetime.now().strftime('%H:%M')} 更新</div>
</div>

<div class="container">

<!-- KPI -->
<div class="kpi-grid">
    <div class="kpi-card">
        <div class="kpi-title">订单总量</div>
        <div class="kpi-value" style="color:#6366F1">{total}</div>
        <div class="kpi-sub">我方 {len(ours)} | 竞争方 {len(comps)}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">完成率</div>
        <div class="kpi-value" style="color:#22C55E">{done/total*100:.1f}%</div>
        <div class="kpi-sub">{done}已送达 / {canc}取消</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">平均配送时长</div>
        <div class="kpi-value" style="color:#F59E0B">{avg_time:.0f}min</div>
        <div class="kpi-sub">中位 {median_time:.0f}min</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">午峰峰值</div>
        <div class="kpi-value" style="color:#EC4899">{peak_cnt}</div>
        <div class="kpi-sub">{peak_h:02d}:00-{peak_h:02d}:59</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">超60min订单</div>
        <div class="kpi-value" style="color:#F97316">{(df['配送时长_min'] > 60).sum()}</div>
        <div class="kpi-sub">占比 {(df['配送时长_min'] > 60).sum()/done*100:.1f}%</div>
    </div>
</div>

<!-- ══ 核心：人均20单达标 ══ -->
<div class="section">
    <h2>🎯 核心：各点位距「人均20单」补贴门槛</h2>
    <div class="chart-box">{fig_gap.to_html(full_html=False, include_plotlyjs=False, div_id='chart_gap')}</div>
    <div class="note-box">
        <strong>补贴条件</strong>：人均≥20单 <b>且</b> 至少1人满3h | 公式：(T-1)×80元/天
        | 当前仅5个我方站点有编制数据，<b>和业广场达标</b>（62单/3人=20.7单/人），其余4站未达标
    </div>
</div>

<!-- ══ 订单总览 ══ -->
<div class="section">
    <h2>📊 订单总览</h2>
    <div class="chart-box">{fig_bar.to_html(full_html=False, include_plotlyjs=False, div_id='chart_bar')}</div>
    <div class="chart-grid">
        <div class="chart-box">{fig_hour.to_html(full_html=False, include_plotlyjs=False, div_id='chart_hour')}</div>
        <div class="chart-box">{fig_time.to_html(full_html=False, include_plotlyjs=False, div_id='chart_time')}</div>
    </div>
</div>

<!-- ══ 站点明细 ══ -->
<div class="section">
    <h2>📋 站点明细</h2>
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

<!-- ══ 竞争方站点（独立子项） ══ -->
<div class="section-sub">
    <h2>🔴 竞争方站点（独立子项·不参与我方对比）</h2>
    <div class="chart-box">{fig_comp.to_html(full_html=False, include_plotlyjs=False, div_id='chart_comp')}</div>
    <div class="note-box">
        <strong>说明</strong>：新中国大厦(72单)、新亚洲电子城(47单)、孙逸仙北院(38单)为竞争方开设点位。
        编制数据未知，无法计算人均单量。仅作信息备案，不作为我方运营分析依据。
    </div>
</div>

<div class="note-box" style="margin-top:16px;">
    <strong>数据说明</strong><br>
    · 时间窗口：2026-06-17 07:54~15:55 · 仅含分段履约站点 · 已排除4个大学城常规站点<br>
    · 5个站点编制：绿地星玥5人、和业广场3人、万菱/金鹰/华林各2人，其余站点待补充<br>
    · 配送时长=送达-下单（含商家出餐全程）
</div>

</div>
</body>
</html>"""

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f'[OK] {OUTPUT}')
print(f'     {total} orders | {len(st)} stations | ours={len(st_ours)} comp={len(st_comps)}')
