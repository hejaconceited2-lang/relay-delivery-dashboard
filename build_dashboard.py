"""
接力送 · 运营看板 — 统一构建脚本
用法:
  python build_dashboard.py 2026-06-18          # 构建指定日期
  python build_dashboard.py --all               # 重建所有日期
  python build_dashboard.py --update-index      # 仅更新总主页
"""
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sys, os, glob, json

# ════════════════════════════════════════════════════════
# 站点编制配置（仅作回退：当天无骑手数据时使用）
# 编制优先从数据自动检测：经手骑手2~N 不重复人数
# ════════════════════════════════════════════════════════
KNOWN_STAFF = {
    '分段履约广州绿地星玥': 4, '分段履约广州万菱广场': 2,
    '分段履约广州和业广场': 3, '分段履约广州金鹰大厦': 2,
    '分段履约广州华林国际C馆': 2, '分段履约广州中大附属第六医院': 6,
    '分段履约广州珠江国际轻纺城': 3, '分段履约广州万科欧泊': 3,
    '分段履约广州孙逸仙北院': 2, '分段履约广州新亚洲电子城': 2,
    '分段履约广州新中国大厦': 3,
    '分段履约广州中大附三岭南医院': 3,
    '分段履约广州汇德国际': 2,
    '分段履约广州云升科技园': 2,
}

# 竞争方站点
COMPETITORS = {'分段履约广州新中国大厦', '分段履约广州新亚洲电子城', '分段履约广州孙逸仙北院'}

# 点位归属人（我方站点）
STATION_OWNER = {
    '分段履约广州中大附属第六医院': '陈贤乡',
    '分段履约广州和业广场': '公司',
    '分段履约广州珠江国际轻纺城': '赵金荣',
    '分段履约广州绿地星玥': '赵金荣',
    '分段履约广州中大附三岭南医院': '欧金标',  # 6.20起
    '分段履约广州万菱广场': '公司',
    '分段履约广州金鹰大厦': '公司',
    '分段履约广州汇德国际': '公司',
    '分段履约广州华林国际C馆': '公司',
    '分段履约广州云升科技园': '欧金标',
    '分段履约广州万科欧泊': '赵金荣',
}

# UE 参数（推广期）
SETTLEMENT_PRICE = 2.5     # 结算价 元/单
RIDER_FEE = 1.0            # 骑手费率 元/单 (骑手↔美团, 非我方收入)
LABOR_RATE = 30            # 人力时薪 元/h
HOURS_PER_PERSON = 3       # 人均日工时 h
MATERIAL_PER_STATION = 100 / 30  # 物料摊销 元/天/站
SUBSIDY_PER_EXTRA = 80     # 补贴 (T-1)x80 元/天
PER_PERSON_THRESHOLD = 20  # 补贴门槛 人均单量

# 日期特定编制覆盖（仅记录与基准不同的日期）
# 格式: "YYYY-MM-DD" -> {站点: 编制}
# 06-17: 中大附属第六医院尚未从2人扩到6人，万科欧泊3人
STAFF_OVERRIDES = {
    '2026-06-17': {
        '分段履约广州中大附属第六医院': 2,  # 6.18才确认编制
    },
}

# 站点级工时覆盖（小时/人/天，默认 HOURS_PER_PERSON=3）
# 营业时间长的站点人工成本更高
STATION_HOURS = {
    '分段履约广州绿地星玥': 10,  # 营业10h
}

# 站点级时薪覆盖（元/h，默认 LABOR_RATE=30）
STATION_LABOR_RATE = {
    '分段履约广州绿地星玥': 23,  # 人工23元/h
}

# 日期特定工时覆盖（优先级高于 STATION_HOURS）
HOURS_OVERRIDES = {
    '2026-06-18': {
        '分段履约广州华林国际C馆': 1.5,  # 双人各1.5h
    },
}

# ════════════════════════════════════════════════════════
# Plotly 暗色模板
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

PLOTLY_CONFIG = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['zoom2d', 'pan2d', 'select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d'],
    'scrollZoom': False,
    'doubleClick': False,
    'showTips': False,
    'responsive': True,
    'displaylogo': False,
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ════════════════════════════════════════════════════════
# 核心逻辑
# ════════════════════════════════════════════════════════

def dark_fig(fig):
    fig.update_layout(**DARK_LAYOUT)
    return fig


def make_hourly_chart(sdf, title='分时订单量', color='#818cf8'):
    hourly = sdf.groupby('hour').size().sort_index()
    if hourly.empty:
        return '<p style="color:#64748b">无数据</p>'
    hour_labels = [f'{h:02d}:00-{h+1:02d}:00' for h in hourly.index]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hour_labels, y=hourly.values,
        marker_color=color, text=hourly.values, textposition='outside',
        hovertemplate='%{x}<br>%{y}单<extra></extra>'
    ))
    ymax = hourly.values.max()
    fig.update_layout(title=title, height=260, xaxis_tickangle=-45, yaxis_title=None,
                      yaxis_range=[0, ymax * 1.2])
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


def make_dual_timeline(sdf, title='到达→送达时间线', color_arrival='#38bdf8', color_delivery='#34d399'):
    """到达点位(骑手1经手) vs 送达 分时对比"""
    arrival = sdf.loc[sdf['骑手1经手_dt'].notna(), 'arrival_hour'].dropna()
    delivery = sdf.loc[sdf['送达时间_dt'].notna(), 'delivery_hour'].dropna()

    if len(arrival) == 0 and len(delivery) == 0:
        return '<p style="color:#64748b">无时间数据</p>'

    hours = sorted(set(int(h) for h in arrival.dropna().tolist() + delivery.dropna().tolist() if pd.notna(h)))
    hour_labels = [f'{h:02d}:00-{h+1:02d}:00' for h in hours]

    arr_counts = [int((arrival.astype(int) == h).sum()) for h in hours]
    del_counts = [int((delivery.astype(int) == h).sum()) for h in hours]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hour_labels, y=arr_counts, name='到达点位',
        marker_color=color_arrival,
        text=[v if v > 0 else '' for v in arr_counts], textposition='outside',
        textfont=dict(color='#bae6fd', size=10),
        hovertemplate='到达 %{x}<br>%{y}单<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        x=hour_labels, y=del_counts, name='已送达',
        marker_color=color_delivery,
        text=[v if v > 0 else '' for v in del_counts], textposition='outside',
        textfont=dict(color='#a7f3d0', size=10),
        hovertemplate='送达 %{x}<br>%{y}单<extra></extra>'
    ))
    ymax = max(max(arr_counts) if arr_counts else 0, max(del_counts) if del_counts else 0)
    fig.update_layout(
        title=title, height=280, xaxis_tickangle=-45, yaxis_title=None,
        yaxis_range=[0, ymax * 1.25],
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
        barmode='group', bargap=0.2, bargroupgap=0.1,
    )
    return dark_fig(fig).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


def kpi_card(title, value, sub='', color='#818cf8'):
    return f"""<div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-sub">{sub}</div></div>"""


def build_station_tab(r, station_charts):
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

    if is_ours and staff:
        meets_per = r['人均单量'] >= 20 if r['人均单量'] else False
        subsidy_per_day = (staff - 1) * 80 if meets_per else 0
        subsidy_color = '#34d399' if subsidy_per_day > 0 else '#f87171'
    else:
        subsidy_per_day = 0
        subsidy_color = '#64748b'

    pickup_html = ''
    if r['已取货'] > 0:
        pickup_html = kpi_card('配送中(已取货)', r['已取货'], '截至数据拉取时间', '#fbbf24')

    tab_id = short.replace(' ', '_')
    orders = r['订单量']
    canc_comp = r['取消赔偿']
    s_hours = r.get('工时', HOURS_PER_PERSON)
    s_rate = r.get('时薪', LABOR_RATE)
    staff_editable = 'kpi-editable' if is_ours and staff else ''
    return f"""
    <div class="tab-panel" id="tab_{tab_id}" data-station="{short}" data-orders="{orders}" data-staff="{staff or 0}" data-ours="{1 if is_ours else 0}" data-canc-comp="{canc_comp or 0}" data-hours="{s_hours}" data-rate="{s_rate}">
        <a href="javascript:switchTab('overview')" class="back-link">&larr; 返回总览</a>
        <div class="kpi-grid">
            {kpi_card('订单量', orders, f"完成率 {r['完成率']}%", '#818cf8')}
            {kpi_card('已完成', r['已完成'], f"已取消 {r['已取消']}", '#34d399')}
            {pickup_html}
            <div class="kpi-card {staff_editable}"{' onclick="editStaff(&quot;' + tab_id + '&quot;, this)"' if is_ours and staff else ''}>
                <div class="kpi-title">编制 {'✎' if is_ours and staff else ''}</div>
                <div class="kpi-value staff-val" style="color:#a78bfa">{staff}人</div>
                <div class="kpi-sub"></div>
            </div>
            {kpi_card('归属人', r.get('归属人', '') or '—', '', '#e2e8f0')}
            <div class="kpi-card">
                <div class="kpi-title">人均单量</div>
                <div class="kpi-value" id="per_{tab_id}" style="color:{'#34d399' if r['达标'] == 'Y' else '#f87171'}">{f"{r['人均单量']}单/人" if r['人均单量'] else 'N/A'}</div>
                <div class="kpi-sub" id="per_sub_{tab_id}">{status_note}</div>
            </div>
            <div class="kpi-card" id="subsidy_card_{tab_id}">
                <div class="kpi-title">今日补贴</div>
                <div class="kpi-value" id="subsidy_{tab_id}" style="color:{subsidy_color}">{subsidy_per_day}元</div>
                <div class="kpi-sub" id="subsidy_formula_{tab_id}">{f'({staff}-1)x80' if is_ours and staff else 'N/A'}</div>
            </div>
            {kpi_card('平均配送', f"{r['平均配送min']}min" if pd.notna(r['平均配送min']) else 'N/A', f"中位 {r['中位配送min']}min", '#fbbf24')}
            {kpi_card('超60min', r['超60min'], f"最长 {r['最长配送min']}min" if pd.notna(r['最长配送min']) else '', '#fb923c')}
        </div>

""" + (f"""
        <div class="profit-line" id="profit_line_{tab_id}">
            <span>结算 ¥{orders * 2.5:,.0f}</span>
            <span>人力 -¥{staff * s_hours * s_rate:,.0f}</span>
            <span>补贴 {'+¥' + str(subsidy_per_day) if subsidy_per_day > 0 else '0'}</span>
            <span>取消赔偿 -¥{int(canc_comp):,}</span>
            <span class="profit-net-value" id="profit_net_{tab_id}" style="color:{'#34d399' if orders*2.5 + subsidy_per_day - staff*s_hours*s_rate - MATERIAL_PER_STATION - canc_comp >= 0 else '#f87171'}">净利 ¥{orders*2.5 + subsidy_per_day - staff*s_hours*s_rate - MATERIAL_PER_STATION - canc_comp:+,.0f}</span>
        </div>
""" if is_ours and staff else '') + f"""
        <div class="note-box" id="note_{tab_id}">
            <strong><span id="badge_{tab_id}">{badge}</span> {short}</strong> | <span id="status_{tab_id}">{status_note}</span>
            {'| 补贴条件：人均>=20单 且 >=1人满3h' if is_ours and staff else ''}
        </div>

        <div class="chart-grid">
            <div class="chart-box">{charts['hourly']}</div>
            <div class="chart-box">{charts['time']}</div>
        </div>

        <div class="section-chart" style="margin-top:16px;">
            <h2>到达→送达时间线</h2>
            {charts['timeline']}
        </div>
    </div>"""


def find_xls(date_dir):
    """在日期目录中查找数据文件 (xls/xlsx)"""
    candidates = glob.glob(os.path.join(date_dir, '*.xls')) + glob.glob(os.path.join(date_dir, '*.xlsx'))
    if not candidates:
        raise FileNotFoundError(f'在 {date_dir} 中未找到数据文件 (xls/xlsx)')
    # 优先选最新的文件
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def process_date(date_str):
    """处理单个日期的数据并生成看板"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = date_obj.strftime('%Y-%m-%d')
    date_short = date_obj.strftime('%y-%m-%d')  # YY-MM-DD for directory
    date_dir = os.path.join(BASE_DIR, date_short)

    if not os.path.isdir(date_dir):
        raise FileNotFoundError(f'日期目录不存在: {date_dir}')

    input_path = find_xls(date_dir)
    output_html = os.path.join(date_dir, 'operations_dashboard.html')
    index_html = os.path.join(date_dir, 'index.html')
    root_html = os.path.join(BASE_DIR, f'{date_obj.strftime("%m%d")}.html')  # root 0618.html

    print(f'[{date_str}] 读取: {os.path.basename(input_path)}')

    df = pd.read_excel(input_path)
    df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

    # 预处理
    df['下单时间_dt'] = pd.to_datetime(df['下单时间'], errors='coerce')
    df['送达时间_dt'] = pd.to_datetime(df['送达时间'], errors='coerce')
    df['骑手1经手_dt'] = pd.to_datetime(df['骑手1经手时间'], errors='coerce')
    df['hour'] = df['下单时间_dt'].dt.hour
    df['arrival_hour'] = df['骑手1经手_dt'].dt.hour.astype('Int64')  # 到达点位时段
    df['delivery_hour'] = df['送达时间_dt'].dt.hour.astype('Int64')   # 送达时段
    mask_done = df['送达时间_dt'].notna()
    df.loc[mask_done, '配送时长_min'] = (
        df.loc[mask_done, '送达时间_dt'] - df.loc[mask_done, '下单时间_dt']
    ).dt.total_seconds() / 60
    # 接力配送时长: 到达→送达
    mask_arrival = df['骑手1经手_dt'].notna() & mask_done
    df.loc[mask_arrival, '接力时长_min'] = (
        df.loc[mask_arrival, '送达时间_dt'] - df.loc[mask_arrival, '骑手1经手_dt']
    ).dt.total_seconds() / 60

    t_min = df['下单时间_dt'].min()
    t_max = df['下单时间_dt'].max()

    # 时间覆盖判断
    total_minutes = (t_max - t_min).total_seconds() / 60
    if total_minutes > 900:  # > 15小时算近全天
        coverage_label = '全天数据'
        coverage_color = '#34d399'
    elif total_minutes > 600:
        coverage_label = '近全天数据'
        coverage_color = '#34d399'
    else:
        coverage_label = '非全天数据'
        coverage_color = '#fbbf24'

    # 应用日期特定编制覆盖
    staff = KNOWN_STAFF.copy()
    if date_str in STAFF_OVERRIDES:
        staff.update(STAFF_OVERRIDES[date_str])

    # ── 从经手骑手2~N 自动检测各站编制（二段及以后接力人员）──
    # 编制 = 数据中实际出现的接力人员数（经手骑手2/3/4/5...）
    # 一段（经手骑手1）是美团骑手，不参与我方编制
    actual_staff = {}  # 站点 → 实际人数（与编制统一）
    staff_detail = {}  # 站点 → 骑手名单
    # 自动发现所有"经手骑手"列（排除经手骑手1 = 一段美团骑手）
    rider_cols = [c for c in df.columns
                  if c.startswith('经手骑手') and c != '经手骑手1']
    if not rider_cols:
        rider_cols = ['经手骑手2', '经手骑手3']  # 回退兼容

    for s in df['站点名称'].unique():
        if s in COMPETITORS:
            actual_staff[s] = staff.get(s, 0)
            continue
        sdf = df[df['站点名称'] == s]
        riders = set()
        for col in rider_cols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        detected = len(riders)
        configured = staff.get(s)

        if detected > 0:
            # 用自动检测值作为编制
            staff[s] = detected
            actual_staff[s] = detected
            staff_detail[s] = riders
            if configured and detected != configured:
                names = '、'.join(sorted(riders))
                print(f'  [编制更新] {s.replace("分段履约广州","")}: {configured}→{detected}人 — {names}')
        elif configured:
            # 无骑手数据时回退到配置值
            actual_staff[s] = configured
            staff_detail[s] = set()
        else:
            actual_staff[s] = 0
            staff_detail[s] = set()

    # 分类
    df['归属'] = df['站点名称'].apply(lambda s: '竞争方' if s in COMPETITORS else '我方')

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
        stf_configured = staff.get(s)       # 编制人数（用于补贴门槛）
        stf_actual = actual_staff.get(s, stf_configured)  # 实际人数（用于人工成本）
        stf = stf_configured                # 默认用编制
        per_person = cnt / stf_configured if stf_configured else None  # 人均用编制算

        if stf and per_person:
            gap = 20 - per_person
            meets = per_person >= 20
            gap_label = f'达标 (+{(-gap):.0f}单)' if meets else f'还差 {gap:.0f} 单'
        else:
            gap = None; meets = False
            gap_label = '编制未知' if stf is None else '?'

        s_times = sdf.loc[mask_done, '配送时长_min']
        # 取消赔偿: 已取消订单的实付金额合计
        canc_mask = sdf['物流单状态'] == '已取消'
        canc_comp = sdf.loc[canc_mask, '订单实付'].sum() if canc_mask.any() else 0
        owner = STATION_OWNER.get(s, '竞争方' if grp == '竞争方' else '')
        # 站点级工时/时薪覆盖
        s_hours = HOURS_OVERRIDES.get(date_str, {}).get(s,
                  STATION_HOURS.get(s, HOURS_PER_PERSON))
        s_rate = STATION_LABOR_RATE.get(s, LABOR_RATE)
        station_rows.append({
            '站点': s.replace('分段履约广州', ''),
            '全名': s, '归属': grp,
            '订单量': cnt, '已完成': s_done, '已取消': s_canc, '取消赔偿': canc_comp,
            '已取货': s_pickup,
            '完成率': round(s_done / cnt * 100, 1) if cnt else 0,
            '编制': stf_configured,
            '实际人数': stf_actual,
            '人均单量': round(per_person, 1) if per_person else None,
            '距20单缺口': gap,
            '达标': 'Y' if meets else ('N' if stf else '?'),
            '缺口描述': gap_label,
            '归属人': owner,
            '工时': s_hours,
            '时薪': s_rate,
            '平均配送min': round(s_times.mean(), 1) if len(s_times) > 0 else None,
            '中位配送min': round(s_times.median(), 1) if len(s_times) > 0 else None,
            '超60min': int((s_times > 60).sum()),
            '最长配送min': round(s_times.max(), 1) if len(s_times) > 0 else None,
        })

    st = pd.DataFrame(station_rows).sort_values('订单量', ascending=False)
    st_ours = st[st['归属'] == '我方']
    st_comps = st[st['归属'] == '竞争方']

    # rider_check 已在上方自动检测中完成（actual_staff / staff_detail）

    # ── 图表 ──
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
    ymax = known['人均单量'].max()
    fig_gap.update_layout(
        title='各点位距「人均20单」补贴门槛',
        height=420, yaxis_title=None,
        yaxis_range=[0, max(ymax * 1.2, 25)],
        xaxis_tickangle=-30,
    )
    html_gap = dark_fig(fig_gap).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_gap')

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
    bar_max = max(st_ours['订单量'].max(), st_comps['订单量'].max())
    fig_bar.update_layout(
        title='各站点订单量',
        height=380, xaxis_tickangle=-30, yaxis_title=None,
        yaxis_range=[0, bar_max * 1.2],
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    html_bar = dark_fig(fig_bar).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_bar')

    html_hour_all = make_hourly_chart(df, '全站分时订单量', '#818cf8')

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

    # 全站 到达→送达时间线
    relay_median = df.loc[mask_arrival, '接力时长_min'].median()
    relay_title = f'全站 到达→送达时间线（接力耗时中位{relay_median:.0f}min）' if pd.notna(relay_median) else '全站 到达→送达时间线'
    html_dual_all = make_dual_timeline(df, relay_title)

    # Per-station charts
    station_charts = {}
    for _, row in st.iterrows():
        full_name = row['全名']
        short = row['站点']
        sdf = df[df['站点名称'] == full_name]
        color = '#818cf8' if row['归属'] == '我方' else '#f87171'
        s_median = sdf.loc[sdf['骑手1经手_dt'].notna() & sdf['送达时间_dt'].notna(), '接力时长_min'].median()
        timeline_title = f'{short} · 到达→送达时间线'
        if pd.notna(s_median):
            timeline_title += f'（接力中位{s_median:.0f}min）'
        station_charts[full_name] = {
            'hourly': make_hourly_chart(sdf, f'{short} · 分时订单量', color),
            'time': make_time_hist(sdf, f'{short} · 配送时长分布', color),
            'timeline': make_dual_timeline(sdf, timeline_title),
        }

    # ── Tab bar ──
    tab_buttons = ['<button class="tab-btn active" onclick="switchTab(\'overview\')">总览</button>']
    for s in st_ours['全名'].tolist():
        short = s.replace('分段履约广州', '')
        sid = short.replace(' ', '_')
        tab_buttons.append(f'<button class="tab-btn" onclick="switchTab(\'{sid}\')">{short}</button>')
    tab_buttons.append('<span style="margin:0 6px;color:#94A3B8;">|</span>')
    for s in st_comps['全名'].tolist():
        short = s.replace('分段履约广州', '')
        sid = short.replace(' ', '_')
        tab_buttons.append(f'<button class="tab-btn tab-comp" onclick="switchTab(\'{sid}\')">{short}</button>')
    tab_bar = '\n'.join(tab_buttons)

    # ── Overview table ──
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
        owner = r.get('归属人', '') or '—'
        table_html += f"""
    <tr>
        <td><a href="javascript:switchTab('{r['站点'].replace(' ', '_')}')" style="color:#818cf8;cursor:pointer;text-decoration:underline">{r['站点']}</a></td>
        <td>{r['订单量']}</td>
        <td>{r['完成率']}%</td>
        <td>{staff_s}</td>
        <td>{owner}</td>
        <td>{per_s}</td>
        <td><b style="color:{gap_color}">{gap_s}{pickup_s}</b></td>
        <td>{badge}</td>
        <td>{r['平均配送min']}min</td>
        <td>{r['已取消']}</td>
        <td>¥{r['取消赔偿']:,.0f}</td>
    </tr>"""

    done_pct = done / total * 100 if total else 0

    # ── Overview panel ──
    pickup_note = f'注意：{coverage_label}' if pickup == 0 else f'注意：{pickup}单仍在配送中（已取货）'
    tabs_overview = f"""
    <div class="tab-panel active" id="tab_overview">
        <div class="note-box" style="border-left-color:#fbbf24;background:rgba(251,191,36,0.08);margin-bottom:14px;">
            <strong>{pickup_note}</strong> — 时间窗口 {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')}（截至拉取时），
            完成率等指标为当前快照值。
            <button class="export-btn" id="exportStaffBtn" onclick="exportStaffConfig()" style="display:none;float:right;">导出编制配置</button>
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
            <h2>到达→送达时间线（骑手1经手 → 送达完成）</h2>
            {html_dual_all}
            <div class="note-box" style="border-left-color:#38bdf8;">
                <strong>到达点位</strong> = 骑手1经手时间（美团骑手送达大堂）&nbsp;|&nbsp;
                <strong>已送达</strong> = 送达时间（接力上楼完成）&nbsp;|&nbsp;
                时段差反映接力配送耗时
            </div>
        </div>

        <div class="section-chart">
            <h2>站点明细（点击跳转详页）</h2>
            <div style="max-height:450px;overflow:auto;">
            <table>
                <thead><tr>
                    <th>站点</th><th>订单量</th><th>完成率</th><th>编制</th><th>归属人</th>
                    <th>人均单量</th><th>距20单门槛</th><th>达标</th>
                    <th>平均配送</th><th>已取消</th><th>取消赔偿</th>
                </tr></thead>
                <tbody>{table_html}</tbody>
            </table>
            </div>
        </div>
    </div>"""

    # ── All panels ──
    all_panels = [tabs_overview]
    for _, r in st.iterrows():
        all_panels.append(build_station_tab(r, station_charts))
    all_panels_html = '\n'.join(all_panels)

    # ── Full HTML ──
    now_str = datetime.now().strftime('%H:%M')
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · 运营看板 | {date_display}</title>
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
.back-link-header {{
  display: inline-block; margin-bottom: 6px; color: var(--accent);
  font-size: 12px; text-decoration: none; transition: color 0.2s;
}}
.back-link-header:hover {{ color: #a5b4fc; }}

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

.back-link {{
  display:inline-block; margin-bottom:12px; padding:6px 14px;
  background:rgba(129,140,248,0.08); border:1px solid rgba(129,140,248,0.2);
  border-radius:6px; color:var(--accent); font-size:12px; font-weight:500;
  text-decoration:none; transition:all var(--transition);
  cursor:pointer;
}}
.back-link:hover {{
  background:rgba(129,140,248,0.16); border-color:var(--border-glow);
  color:#a5b4fc;
}}
.kpi-editable {{ cursor:pointer; }}
.kpi-editable:hover {{ border-color:var(--warning) !important; }}
.kpi-editable .kpi-title {{ color:var(--warning); }}
.profit-line {{
  display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  padding:8px 16px; margin-bottom:4px;
  background:rgba(15,20,30,0.6); border:1px solid var(--border);
  border-radius:var(--radius-sm); font-size:11.5px; color:var(--text-dim);
}}
.profit-net-value {{ font-weight:700; font-size:13px; margin-left:auto; }}
.export-btn {{
  display:inline-block; margin-left:12px; padding:4px 12px;
  background:rgba(251,191,36,0.1); border:1px solid rgba(251,191,36,0.25);
  border-radius:6px; color:var(--warning); font-size:11px; cursor:pointer;
  transition:all var(--transition);
}}
.export-btn:hover {{ background:rgba(251,191,36,0.2); color:#fcd34d; }}

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
    <a href="index.html" class="back-link-header">&larr; 返回主页</a>
    <h1>接力送 · 运营看板</h1>
    <div class="meta">{date_display} &nbsp;·&nbsp; {total}单 &nbsp;·&nbsp; {len(st)}站（我方{len(st_ours)} + 竞争方{len(st_comps)}）&nbsp;·&nbsp; {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')} &nbsp;·&nbsp; {now_str} 更新 &nbsp;·&nbsp; <span style="color:{coverage_color}">{coverage_label}</span></div>
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

var staffChanges = {{}};  // {{tabId: newStaff}}

function editStaff(tabId, card) {{
    var valEl = card.querySelector('.staff-val');
    var current = parseInt(valEl.textContent);
    var input = prompt('修改编制 (当前 '+current+'人):', current);
    if (input === null || input === '') return;
    var newStaff = parseInt(input);
    if (isNaN(newStaff) || newStaff < 1) return;
    valEl.textContent = newStaff + '人';
    staffChanges[tabId] = newStaff;
    recalcUE(tabId, newStaff);
    updateExportBtn();
}}

function recalcUE(tabId, staff) {{
    var panel = document.getElementById('tab_' + tabId);
    var orders = parseInt(panel.dataset.orders);
    var perPerson = (orders / staff).toFixed(1);
    var meets = perPerson >= 20;
    var subsidy = meets ? (staff - 1) * 80 : 0;

    // 人均单量
    var perEl = document.getElementById('per_' + tabId);
    var perSub = document.getElementById('per_sub_' + tabId);
    if (perEl) {{
        perEl.textContent = perPerson + '单/人';
        perEl.style.color = meets ? '#34d399' : '#f87171';
    }}
    if (perSub) {{
        if (meets) perSub.textContent = '人均' + perPerson + '单 (+' + (perPerson - 20).toFixed(1) + ')';
        else perSub.textContent = '人均' + perPerson + '单 (差' + (20 - perPerson).toFixed(1) + '单)';
    }}

    // 补贴
    var subEl = document.getElementById('subsidy_' + tabId);
    var subForm = document.getElementById('subsidy_formula_' + tabId);
    if (subEl) {{
        subEl.textContent = subsidy + '元';
        subEl.style.color = subsidy > 0 ? '#34d399' : '#f87171';
    }}
    if (subForm) subForm.textContent = '(' + staff + '-1)x80';

    // 达标badge
    var badgeEl = document.getElementById('badge_' + tabId);
    if (badgeEl) {{
        if (meets) {{
            badgeEl.className = 'badge badge-green';
            badgeEl.textContent = '达标';
        }} else {{
            badgeEl.className = 'badge badge-red';
            badgeEl.textContent = '未达标';
        }}
    }}

    // 状态文字
    var statusEl = document.getElementById('status_' + tabId);
    if (statusEl) {{
        if (meets) statusEl.textContent = '人均' + perPerson + '单 (+' + (perPerson - 20).toFixed(1) + ')';
        else statusEl.textContent = '人均' + perPerson + '单 (差' + (20 - perPerson).toFixed(1) + '单)';
    }}

    // 盈利重算
    var settlement = orders * 2.5;
    var hours = parseFloat(panel.dataset.hours) || 3;
    var rate = parseFloat(panel.dataset.rate) || 30;
    var labor = staff * hours * rate;
    var material = 100/30;
    var cancComp = parseFloat(panel.dataset.cancComp) || 0;
    var lineSubsidy = meets ? (staff - 1) * 80 : 0;
    var profit = settlement + lineSubsidy - labor - material - cancComp;
    var profitLine = document.getElementById('profit_line_' + tabId);
    if (profitLine) {{
        var spans = profitLine.querySelectorAll('span');
        if (spans.length >= 5) {{
            spans[0].textContent = '结算 ¥' + settlement.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[1].textContent = '人力 -¥' + labor.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[2].textContent = '补贴 ' + (lineSubsidy > 0 ? '+¥' + lineSubsidy : '0');
            spans[3].textContent = '取消赔偿 -¥' + cancComp.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[4].textContent = '净利 ¥' + (profit >= 0 ? '+' : '') + profit.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[4].style.color = profit >= 0 ? '#34d399' : '#f87171';
        }}
    }}

    // 存储
    localStorage.setItem('staff_overrides_' + window.location.pathname, JSON.stringify(staffChanges));
}}

function updateExportBtn() {{
    var btn = document.getElementById('exportStaffBtn');
    if (btn) btn.style.display = Object.keys(staffChanges).length ? 'inline-block' : 'none';
}}

// Load saved overrides on page load
document.addEventListener('DOMContentLoaded', function() {{
    var saved = localStorage.getItem('staff_overrides_' + window.location.pathname);
    if (saved) {{
        staffChanges = JSON.parse(saved);
        Object.keys(staffChanges).forEach(function(tabId) {{
            var card = document.querySelector('#tab_' + tabId + ' .kpi-editable');
            if (card) {{
                var newStaff = staffChanges[tabId];
                card.querySelector('.staff-val').textContent = newStaff + '人';
                recalcUE(tabId, newStaff);
            }}
        }});
    }}
    updateExportBtn();
}});

function exportStaffConfig() {{
    var lines = [];
    Object.keys(staffChanges).forEach(function(tabId) {{
        var panel = document.getElementById('tab_' + tabId);
        var station = panel.dataset.station;
        lines.push("        '分段履约广州" + station + "': " + staffChanges[tabId] + ",");
    }});
    if (!lines.length) {{ alert('暂无修改'); return; }}
    var code = "'" + document.title.split('|')[1].trim() + "': {{\\n" + lines.join('\\n') + "\\n    }},";
    navigator.clipboard.writeText(code).then(function() {{
        alert('已复制到剪贴板:\\n\\n' + code + '\\n\\n粘贴到 build_dashboard.py 的 STAFF_OVERRIDES 中');
    }});
}}
</script>

</body>
</html>"""

    # 写入文件
    for path in [output_html, index_html]:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
    # 同步到根目录
    with open(root_html, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'  [OK] {os.path.basename(output_html)} ({total}单, {len(st)}站, {done}送达, {canc}取消)')
    print(f'  [OK] {os.path.basename(root_html)} (根目录同步)')

    # ── 逐站盈亏计算 ──
    station_profits = []
    day_total_revenue = 0
    day_total_labor = 0
    day_total_material = 0
    day_total_subsidy = 0
    day_total_canc_comp = 0
    for _, r in st.iterrows():
        cnt = r['订单量']
        grp = r['归属']
        stf = r['编制']
        per_p = r['人均单量'] if pd.notna(r['人均单量']) else None

        paper = r['编制']         # 编制人数，用于补贴
        actual = r['实际人数']     # 实际人数，用于人工成本
        if grp == '我方' and paper and cnt > 0:
            settlement = cnt * SETTLEMENT_PRICE
            revenue = settlement
            hours_per = r.get('工时', HOURS_PER_PERSON)
            rate = r.get('时薪', LABOR_RATE)
            labor = actual * hours_per * rate
            material = MATERIAL_PER_STATION
            canc_comp = r['取消赔偿']
            meets = per_p and per_p >= PER_PERSON_THRESHOLD
            subsidy = (paper - 1) * SUBSIDY_PER_EXTRA if meets else 0  # 补贴用编制
            profit = revenue + subsidy - labor - material - canc_comp

            station_profits.append({
                '站点': r['站点'],
                '归属': grp,
                '订单量': cnt,
                '编制': paper,
                '实际人数': actual,
                '人均单量': per_p,
                '已取消': r['已取消'],
                '取消赔偿': round(canc_comp, 1),
                '结算收入': round(settlement, 1),
                '人力成本': round(labor, 1),
                '物料': round(material, 1),
                '补贴': round(subsidy, 1),
                '净利': round(profit, 1),
                '达标': r['达标'],
            })
            day_total_revenue += revenue
            day_total_labor += labor
            day_total_material += material
            day_total_subsidy += subsidy
            day_total_canc_comp += canc_comp

    day_profit = round(day_total_revenue + day_total_subsidy - day_total_labor - day_total_material - day_total_canc_comp, 1)

    # ── 生成单日 UE 分析页 ──
    build_ue_page(date_display, total, len(st_ours), station_profits,
                  day_profit, day_total_revenue, day_total_subsidy, day_total_labor,
                  day_total_canc_comp, t_min, t_max)

    # 返回摘要用于更新主页面
    return {
        'date': date_display,
        'total': total,
        'stations': len(st),
        'done': done,
        'canc': canc,
        'time_range': f'{t_min.strftime("%H:%M")}-{t_max.strftime("%H:%M")}',
        'coverage_label': coverage_label,
        'station_profits': station_profits,
        'day_profit': day_profit,
        'day_revenue': round(day_total_revenue, 1),
        'day_subsidy': round(day_total_subsidy, 1),
        'day_labor': round(day_total_labor, 1),
        'day_canc_comp': round(day_total_canc_comp, 1),
    }


def build_ue_page(date_display, total_orders, ours_count, station_profits,
                  day_profit, day_revenue, day_subsidy, day_labor,
                  day_canc_comp, t_min, t_max):
    """生成单日 UE 盈利分析页面 MMDD_ue.html"""
    date_obj = datetime.strptime(date_display, '%Y-%m-%d')
    mdd = date_obj.strftime('%m%d')
    date_short = date_obj.strftime('%y-%m-%d')
    ue_path = os.path.join(BASE_DIR, f'{mdd}_ue.html')
    date_dir = os.path.join(BASE_DIR, date_short)
    ue_dir_path = os.path.join(date_dir, 'ue_analysis.html')

    profit_color = '#34d399' if day_profit >= 0 else '#f87171'
    day_material = ours_count * MATERIAL_PER_STATION

    # ── KPI 卡片 ──
    profit_rate = (day_profit / day_revenue * 100) if day_revenue > 0 else 0

    # ── 站点净利排名图 ──
    sp_sorted = sorted(station_profits, key=lambda x: x['净利'])
    fig_rank = go.Figure()
    fig_rank.add_trace(go.Bar(
        y=[sp['站点'] for sp in sp_sorted],
        x=[sp['净利'] for sp in sp_sorted],
        orientation='h',
        marker_color=['#34d399' if sp['净利'] >= 0 else '#f87171' for sp in sp_sorted],
        text=[f'¥{sp["净利"]:+,.0f}' for sp in sp_sorted],
        textposition='outside',
        textfont=dict(color='#e2e8f0', size=11),
        hovertemplate='%{y}<br>净利: ¥%{x:+,.0f}<br>单量: %{customdata}单<extra></extra>',
        customdata=[sp['订单量'] for sp in sp_sorted],
    ))
    fig_rank.update_layout(
        title='各站点日净利排名',
        height=max(280, len(sp_sorted) * 34),
        xaxis_title=None, yaxis_title=None,
        xaxis=dict(zeroline=True, zerolinecolor='rgba(148,163,184,0.15)'),
        margin=dict(t=45, b=30, l=100, r=50),
    )
    html_rank = dark_fig(fig_rank).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_rank')

    # ── 收支结构图 ──
    # 收入构成: 结算
    fig_rev = go.Figure()
    rev_settlement = sum(sp['结算收入'] for sp in station_profits)
    fig_rev.add_trace(go.Pie(
        labels=['结算收入'],
        values=[rev_settlement],
        marker_colors=['#818cf8'],
        hole=0.5, textinfo='label+value',
        textfont=dict(color='#e2e8f0', size=11),
    ))
    fig_rev.update_layout(title='收入构成', height=280, showlegend=False,
                          margin=dict(t=45, b=10, l=10, r=10))
    html_rev = dark_fig(fig_rev).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_rev')

    # 成本构成: 人力 vs 物料 vs 取消赔偿
    fig_cost = go.Figure()
    fig_cost.add_trace(go.Pie(
        labels=['人力成本', '物料摊销', '取消赔偿'],
        values=[day_labor, day_material, day_canc_comp],
        marker_colors=['#f87171', '#fb923c', '#ef4444'],
        hole=0.5, textinfo='label+value',
        textfont=dict(color='#e2e8f0', size=11),
    ))
    fig_cost.update_layout(title='成本构成', height=280, showlegend=False,
                           margin=dict(t=45, b=10, l=10, r=10))
    html_cost = dark_fig(fig_cost).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_cost')

    # ── 站点明细表 ──
    rows = ''
    for sp in sorted(station_profits, key=lambda x: x['净利'], reverse=True):
        pc = '#34d399' if sp['净利'] >= 0 else '#f87171'
        subsidy_str = f'+{sp["补贴"]:.0f}' if sp['补贴'] > 0 else '0'
        canc_str = f'{sp.get("已取消",0)}单' if sp.get('已取消', 0) > 0 else '0'
        comp_str = f'-¥{sp.get("取消赔偿",0):.0f}' if sp.get('取消赔偿', 0) > 0 else '0'
        rows += f"""
                <tr>
                  <td>{sp['站点']}</td>
                  <td>{sp['订单量']}</td>
                  <td>{canc_str}</td>
                  <td>{sp['编制']}人</td>
                  <td>{sp['人均单量']}单/人</td>
                  <td>¥{sp['结算收入']:,.0f}</td>
                  <td>-¥{sp['人力成本']:,.0f}</td>
                  <td>-¥{sp['物料']:.0f}</td>
                  <td style="color:#f87171">{comp_str}</td>
                  <td>{subsidy_str}</td>
                  <td style="color:{pc};font-weight:600">¥{sp['净利']:+,.0f}</td>
                </tr>"""

    # ── 完整 HTML ──
    now_str = datetime.now().strftime('%H:%M')
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · UE 盈利分析 | {date_display}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
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
  --pink: #f472b6;
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
.header .meta {{ font-size: 12px; color: var(--text-dim); margin-top: 4px; }}
.header .back {{
  display: inline-block; margin-top: 8px; color: var(--accent);
  font-size: 12px; text-decoration: none; transition: color 0.2s;
}}
.header .back:hover {{ color: #a5b4fc; }}

.container {{ max-width:1100px; margin:0 auto; padding:20px 28px 40px; }}

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
}}
.kpi-card:hover {{
  transform:translateY(-2px);
  border-color:var(--border-glow);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px var(--border-glow);
}}
.kpi-title {{
  font-size:10.5px; color:var(--text-muted); font-weight:600;
  text-transform:uppercase; letter-spacing:0.8px;
}}
.kpi-value {{
  font-size:26px; font-weight:800; margin:3px 0;
  font-variant-numeric:tabular-nums; letter-spacing:-1px;
}}
.kpi-sub {{ font-size:11px; color:var(--text-dim); }}

.section {{
  background:var(--surface);
  backdrop-filter:blur(20px);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px; margin-bottom:16px;
}}
.section h2 {{
  font-size:15px; font-weight:700; color:var(--text);
  padding-bottom:10px; margin-bottom:14px;
  border-bottom:1px solid var(--border);
  display:flex; align-items:center; gap:8px;
}}
.section h2::before {{
  content: ''; width:4px; height:18px; border-radius:2px;
  background:var(--accent);
}}

.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{
  background:rgba(30,41,59,0.6); color:var(--text-dim); font-weight:600;
  padding:9px 10px; text-align:left; font-size:10.5px;
  text-transform:uppercase; letter-spacing:0.5px;
}}
td {{
  padding:7px 10px; border-bottom:1px solid rgba(148,163,184,0.06);
  color:var(--text-dim);
}}
tr:last-child td {{ border-bottom:none; }}
tr:hover td {{ background:rgba(129,140,248,0.04); }}

.note-box {{
  background:rgba(129,140,248,0.06);
  border:1px solid rgba(129,140,248,0.15);
  border-left:3px solid var(--accent);
  padding:11px 16px; border-radius:var(--radius-sm);
  margin:14px 0; font-size:12px; color:var(--text-dim);
}}
.note-box strong {{ color:var(--accent); }}

::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:transparent; }}
::-webkit-scrollbar-thumb {{ background:rgba(148,163,184,0.15); border-radius:3px; }}

@media (max-width:768px) {{
  .header {{ padding:16px 18px 10px; }}
  .header h1 {{ font-size:20px; }}
  .container {{ padding:12px 10px 30px; }}
  .chart-grid {{ grid-template-columns:1fr; }}
  .kpi-grid {{ grid-template-columns:repeat(auto-fit, minmax(130px,1fr)); }}
}}
</style>
</head>
<body>

<div class="header">
    <a href="index.html" class="back">&larr; 返回总览</a>
    <h1>UE 盈利分析</h1>
    <div class="meta">{date_display} &nbsp;·&nbsp; {total_orders}单 &nbsp;·&nbsp; {ours_count}站 &nbsp;·&nbsp; {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')} &nbsp;·&nbsp; {now_str} 更新</div>
</div>

<div class="container">

    <div class="note-box">
        <strong>UE 参数</strong> &nbsp;结算 {SETTLEMENT_PRICE}元/单 &nbsp;|&nbsp; 人力 {LABOR_RATE}元/h×{HOURS_PER_PERSON}h &nbsp;|&nbsp; 物料 {MATERIAL_PER_STATION:.1f}元/天/站 &nbsp;|&nbsp; 补贴 (T-1)×{SUBSIDY_PER_EXTRA}元 &nbsp;|&nbsp; 门槛≥{PER_PERSON_THRESHOLD}单/人
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">总收入</div>
            <div class="kpi-value" style="color:#818cf8">¥{day_revenue:,.0f}</div>
            <div class="kpi-sub">结算收入 2.5元/单</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">总人力成本</div>
            <div class="kpi-value" style="color:#f87171">-¥{day_labor:,.0f}</div>
            <div class="kpi-sub">{ours_count}站 × 人均{LABOR_RATE}元/h×{HOURS_PER_PERSON}h</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">总物料</div>
            <div class="kpi-value" style="color:#fb923c">-¥{day_material:,.0f}</div>
            <div class="kpi-sub">{MATERIAL_PER_STATION:.1f}元 × {ours_count}站</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">取消赔偿</div>
            <div class="kpi-value" style="color:#f87171">-¥{day_canc_comp:,.0f}</div>
            <div class="kpi-sub">已取消订单实付金额</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">总补贴</div>
            <div class="kpi-value" style="color:#fbbf24">+¥{day_subsidy:,.0f}</div>
            <div class="kpi-sub">(T-1)×{SUBSIDY_PER_EXTRA}元</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">日净利</div>
            <div class="kpi-value" style="color:{profit_color}">¥{day_profit:+,.0f}</div>
            <div class="kpi-sub">利润率 {profit_rate:+.1f}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">单均净利</div>
            <div class="kpi-value" style="color:{profit_color}">¥{(day_profit/total_orders):+.2f}</div>
            <div class="kpi-sub">每单利润</div>
        </div>
    </div>

    <div class="section">
        <h2>站点日净利排名</h2>
        {html_rank}
    </div>

    <div class="section">
        <h2>收支结构</h2>
        <div class="chart-grid">
            <div>{html_rev}</div>
            <div>{html_cost}</div>
        </div>
    </div>

    <div class="section">
        <h2>站点收支明细</h2>
        <div style="max-height:500px;overflow:auto;">
        <table>
            <thead><tr>
                <th>站点</th><th>单量</th><th>取消</th><th>编制</th><th>人均</th>
                <th>结算</th><th>人力</th><th>物料</th><th>赔偿</th><th>补贴</th><th>净利</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
        </div>
    </div>

</div>

</body>
</html>"""

    for path in [ue_path, ue_dir_path]:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
    print(f'  [OK] {os.path.basename(ue_path)} (UE analysis)')


def update_index(dates_summary):
    """根据所有日期摘要更新根目录 index.html 总主页"""
    # 按日期排序
    dates_summary.sort(key=lambda d: d['date'], reverse=True)

    total_orders = sum(d['total'] for d in dates_summary)
    all_stations = set()
    for d in dates_summary:
        # 从生成的 HTML 中无法直接获取站点列表，用最大值近似
        pass
    max_stations = max(d['stations'] for d in dates_summary) if dates_summary else 0
    num_dates = len(dates_summary)
    latest_date = dates_summary[0]['date'] if dates_summary else 'N/A'

    # ── 走势图 ──
    trend_data = sorted(dates_summary, key=lambda x: x['date'])
    trend_dates = [f"{int(d['date'][5:7])}/{int(d['date'][8:10])}" for d in trend_data]  # M/D
    trend_orders = [d['total'] for d in trend_data]
    trend_profits = [d.get('day_profit', 0) for d in trend_data]
    trend_revenues = [d.get('day_revenue', 0) for d in trend_data]
    trend_labors = [d.get('day_labor', 0) for d in trend_data]
    trend_cancs = [d.get('day_canc_comp', 0) for d in trend_data]
    trend_materials = [len(trend_data) * 0]  # placeholder, compute per-date

    # 图1: 日单量 + 日净利
    fig_trend1 = go.Figure()
    fig_trend1.add_trace(go.Bar(
        x=trend_dates, y=trend_orders, name='订单量',
        marker_color='#818cf8', text=trend_orders, textposition='outside',
        textfont=dict(color='#c7d2fe', size=10),
    ))
    fig_trend1.add_trace(go.Scatter(
        x=trend_dates, y=trend_profits, name='日净利',
        mode='lines+markers', yaxis='y2',
        line=dict(color='#34d399' if trend_profits[-1] >= 0 else '#f87171', width=2),
        marker=dict(size=6), text=[f'¥{p:+,.0f}' for p in trend_profits],
        textposition='top center', textfont=dict(color='#e2e8f0', size=10),
    ))
    fig_trend1.update_layout(
        title='日单量 & 净利走势',
        height=320, xaxis_tickangle=-30,
        yaxis=dict(title=None, gridcolor='rgba(148,163,184,0.06)'),
        yaxis2=dict(title=None, overlaying='y', side='right', showgrid=False),
        legend=dict(orientation='h', y=1.12, x=0),
        margin=dict(t=50, b=50, l=45, r=50),
    )
    html_trend1 = dark_fig(fig_trend1).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='trend1')

    # 图2: 收入与成本堆叠
    fig_trend2 = go.Figure()
    fig_trend2.add_trace(go.Bar(
        x=trend_dates, y=trend_revenues, name='总收入',
        marker_color='#818cf8',
    ))
    fig_trend2.add_trace(go.Bar(
        x=trend_dates, y=[-(l + d.get('day_canc_comp', 0) + d.get('stations', 0) * MATERIAL_PER_STATION) for l, d in zip(trend_labors, trend_data)],
        name='成本(人力+物料+赔偿)',
        marker_color='#f87171',
    ))
    fig_trend2.add_trace(go.Bar(
        x=trend_dates, y=[d.get('day_subsidy', 0) for d in trend_data],
        name='补贴', marker_color='#fbbf24',
    ))
    fig_trend2.update_layout(
        title='收支结构',
        height=320, xaxis_tickangle=-30, barmode='relative',
        yaxis=dict(title=None, gridcolor='rgba(148,163,184,0.06)'),
        legend=dict(orientation='h', y=1.12, x=0),
        margin=dict(t=50, b=50, l=45, r=25),
    )
    html_trend2 = dark_fig(fig_trend2).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='trend2')

    trends_html = f"""
      <div class="trend-sidebar">
        <div class="trend-box">{html_trend1}</div>
        <div class="trend-box">{html_trend2}</div>
      </div>"""

    # 生成日期卡片
    cards_html = ''
    for d in dates_summary:
        is_latest = d['date'] == latest_date
        if is_latest:
            badge_html = f' <span class="badge {"badge-new" if d["coverage_label"] in ("全天数据","近全天数据") else "badge-pending"}" style="margin-left:8px;">{d["coverage_label"]}</span>'
        else:
            badge_html = ''
        mdd = datetime.strptime(d['date'], '%Y-%m-%d').strftime('%m%d')
        profit_color = '#34d399' if d.get('day_profit', 0) >= 0 else '#f87171'

        # 盈利摘要行 → 链接到单日 UE 分析页
        profit_row = ''
        if d.get('day_profit') is not None:
            profit_row = f"""
        <a href="{mdd}_ue.html" class="profit-summary">
          <span>结算 ¥{d.get('day_revenue',0):,.0f}</span>
          <span>人力 -¥{d.get('day_labor',0):,.0f}</span>
          <span>赔偿 -¥{d.get('day_canc_comp',0):,.0f}</span>
          <span>补贴 +¥{d.get('day_subsidy',0):,.0f}</span>
          <span class="profit-net" style="color:{profit_color}">日净利 {d['day_profit']:+,.0f}元</span>
          <span class="profit-arrow">&rarr;</span>
        </a>"""

        cards_html += f"""
      <div class="day-card">
        <a href="{mdd}.html" class="day-card-link">
          <div class="row">
            <div>
              <div class="date">{d['date']}{badge_html}</div>
              <div class="stats">
                <span>{d['total']} 单</span><span>{d['stations']} 站</span><span>{d['done']} 送达</span><span>{d['canc']} 取消</span><span>{d['time_range']}</span>
              </div>
            </div>
            <span class="arrow">&rarr;</span>
          </div>
        </a>
        {profit_row}
      </div>"""

    now_str = datetime.now().strftime('%m-%d %H:%M')
    index_path = os.path.join(BASE_DIR, 'index.html')

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接力送 · 日订单运营看板</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
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
  --pink: #f472b6;
  --radius: 14px;
  --radius-sm: 10px;
  --transition: 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
  padding: 32px 40px 20px;
  backdrop-filter: blur(20px);
  overflow: hidden;
}}
.header::after {{
  content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--success), var(--pink), var(--warning));
  opacity: 0.6;
}}
.header h1 {{
  font-size: 28px; font-weight: 800; letter-spacing: -0.5px;
  background: linear-gradient(135deg, #e2e8f0 0%, #818cf8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header .sub {{
  font-size: 13px; color: var(--text-dim); margin-top: 6px;
}}

.container {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px 60px; }}

.main-layout {{ display: flex; gap: 20px; align-items: flex-start; }}
.main-cards {{ flex: 1; min-width: 0; }}
.trend-sidebar {{
  width: 440px; flex-shrink: 0; display: flex; flex-direction: column; gap: 16px;
  position: sticky; top: 20px;
}}
.trend-box {{
  background: var(--surface);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
}}

.day-card {{
  position: relative;
  background: var(--surface);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 14px;
  transition: all var(--transition);
  overflow: hidden;
}}
.day-card:hover {{
  border-color: var(--border-glow);
  box-shadow: 0 12px 40px rgba(0,0,0,0.35), 0 0 0 1px var(--border-glow);
}}
.day-card-link {{
  display: block; padding: 22px 26px;
  text-decoration: none; color: inherit; transition: all var(--transition);
}}
.day-card-link:hover {{ transform: translateY(-2px); }}
.day-card .row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}}
.day-card .date {{
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.3px;
}}
.day-card .stats {{
  display: flex;
  gap: 18px;
  font-size: 13px;
  color: var(--text-dim);
  margin-top: 8px;
  flex-wrap: wrap;
}}
.day-card .badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}}
.badge-new {{
  background: rgba(52,211,153,0.12); color: #34d399;
  border: 1px solid rgba(52,211,153,0.25);
}}
.badge-pending {{
  background: rgba(251,191,36,0.1); color: #fbbf24;
  border: 1px solid rgba(251,191,36,0.2);
}}
.day-card .arrow {{
  font-size: 18px;
  color: var(--text-muted);
  transition: all var(--transition);
}}
.day-card-link:hover .arrow {{ color: var(--accent); transform: translateX(4px); }}

/* 盈利摘要 — 链接到 UE 分析页 */
.profit-summary {{
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  padding: 10px 26px;
  border-top: 1px solid var(--border);
  background: rgba(129,140,248,0.03);
  font-size: 12px; color: var(--text-dim);
  text-decoration: none;
  transition: background var(--transition);
}}
.profit-summary:hover {{ background: rgba(129,140,248,0.1); }}
.profit-net {{ font-weight: 700; font-size: 13px; margin-left: auto; }}
.profit-arrow {{ font-size: 14px; color: var(--text-muted); transition: transform 0.2s; }}
.profit-summary:hover .profit-arrow {{ color: var(--accent); transform: translateX(2px); }}

.summary-bar {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 28px;
}}
.summary-item {{
  background: var(--surface);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 16px;
  text-align: center;
}}
.summary-item .label {{
  font-size: 10px; color: var(--text-muted); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.8px;
}}
.summary-item .value {{
  font-size: 26px; font-weight: 800; margin: 4px 0;
}}

.footer {{
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}}

@media (max-width: 600px) {{
  .header {{ padding: 24px 20px 16px; }}
  .header h1 {{ font-size: 22px; }}
  .container {{ padding: 16px 12px 40px; }}
  .summary-bar {{ grid-template-columns: repeat(2, 1fr); }}
  .main-layout {{ flex-direction: column; }}
  .trend-sidebar {{ width: 100%; position: static; }}
  .day-card .row {{ flex-wrap: wrap; }}
}}
</style>
</head>
<body>

<div class="header">
  <h1>接力送 · 日订单运营看板</h1>
  <div class="sub">分段履约站点每日订单数据 &middot; 自动更新 &middot; <span id="updateTime">{now_str}</span></div>
</div>

<div class="container">

  <div class="summary-bar">
    <div class="summary-item">
      <div class="label">已覆盖天数</div>
      <div class="value" style="color:#818cf8">{num_dates}</div>
    </div>
    <div class="summary-item">
      <div class="label">累计订单</div>
      <div class="value" style="color:#34d399">{total_orders:,}</div>
    </div>
    <div class="summary-item">
      <div class="label">覆盖站点</div>
      <div class="value" style="color:#a78bfa">{max_stations}</div>
    </div>
    <div class="summary-item">
      <div class="label">最近更新</div>
      <div class="value" style="color:#fbbf24;font-size:14px;">{latest_date[5:]}</div>
    </div>
  </div>
  <div class="main-layout">
    <div class="main-cards">
{cards_html}
    </div>
{trends_html}
  </div>
  <div class="footer">
    接力送 &middot; 楼宇末端配送运营数据 &nbsp;|&nbsp; 数据来源: 美团校园订单详情导出
  </div>

</div>

</body>
</html>"""

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f'\n[OK] 总主页已更新: {total_orders:,}单 / {num_dates}天 / {max_stations}站')


def discover_dates():
    """扫描项目目录，发现所有日期目录 (YY-MM-DD 格式)"""
    dates = []
    for name in os.listdir(BASE_DIR):
        # 匹配 YY-MM-DD 格式的目录名
        if len(name) == 8 and name[2] == '-' and name[5] == '-':
            dir_path = os.path.join(BASE_DIR, name)
            if os.path.isdir(dir_path):
                # 检查是否有 xls 数据文件
                if glob.glob(os.path.join(dir_path, '*.xls')) or glob.glob(os.path.join(dir_path, '*.xlsx')):
                    yy, mm, dd = name.split('-')
                    year = '20' + yy
                    dates.append(f'{year}-{mm}-{dd}')
    return sorted(dates)


# ════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print('可用日期:')
        for d in discover_dates():
            print(f'  {d}')
        sys.exit(1)

    arg = sys.argv[1]

    if arg == '--all':
        dates = discover_dates()
        if not dates:
            print('未发现任何日期目录。')
            sys.exit(1)
        print(f'重建 {len(dates)} 个日期的看板...\n')
        summaries = []
        for d in dates:
            try:
                s = process_date(d)
                summaries.append(s)
            except Exception as e:
                print(f'  [{d}] 错误: {e}')
        print()
        update_index(summaries)

    elif arg == '--update-index':
        dates = discover_dates()
        summaries = []
        for d in dates:
            try:
                s = process_date(d)
                summaries.append(s)
                print(f'  [{d}] {s["total"]}单 / {s["stations"]}站')
            except Exception as e:
                print(f'  [{d}] 跳过: {e}')
        print()
        update_index(summaries)

    else:
        # 单日期模式
        date_str = arg
        try:
            summary = process_date(date_str)
            summaries = [summary]
            # 同时收集其他日期摘要以更新主页面
            for d in discover_dates():
                if d == date_str:
                    continue
                try:
                    s = process_date(d)
                    summaries.append(s)
                except Exception as e:
                    print(f'  [{d}] 跳过: {e}')
            print()
            update_index(summaries)
        except Exception as e:
            print(f'错误: {e}')
            sys.exit(1)
