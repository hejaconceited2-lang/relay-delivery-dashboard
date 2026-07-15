"""
接力送 · 运营看板 — 统一构建脚本
用法:
  python build_dashboard.py 2026-06-18          # 构建指定日期(增量)
  python build_dashboard.py 2026-06-18 --sync   # 同步本地计薪表+构建(增量)
  python build_dashboard.py 2026-06-18 --full   # 全量重建所有日期
  python build_dashboard.py --all               # 重建所有日期
  python build_dashboard.py --update-index      # 仅更新总主页

计薪表: 本地手动维护 接力送真实人力计薪/接力送计薪表格.xlsx, 不再从腾讯文档拉取

标准更新流程:
  1. 下载订单xls → 放入 26-06-XX/ 目录
  2. 更新计薪表 (如需) → 接力送真实人力计薪/接力送计薪表格.xlsx
  3. python build_dashboard.py 2026-06-XX --sync
  4. git add -A && git commit && git push
"""
import sys
import io
# 强制 stdout 使用 UTF-8，避免 Windows GBK 环境下中文乱码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import sys, os, glob, json

# 动态加载计薪表解析器
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
from parse_payroll import parse_payroll

def _load_payroll_config():
    """从计薪表xlsx动态加载配置, 替代硬编码"""
    payroll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '接力送真实人力计薪', '接力送计薪表格.xlsx')
    if os.path.exists(payroll_path):
        daily_labor, daily_headcount, actual_staff = parse_payroll(payroll_path)
        # 用解析结果覆盖硬编码
        globals()['DAILY_LABOR_COST'] = daily_labor
        globals()['ACTUAL_STAFF_OVERRIDES'] = daily_headcount
        globals()['ACTUAL_STAFF'] = actual_staff
        return True
    return False

# ════════════════════════════════════════════════════════
# 系统登记人员回退配置（仅作回退：当天无骑手数据时使用）
# 系统登记人员优先从数据自动检测：经手骑手2~N 不重复人数
# ════════════════════════════════════════════════════════
KNOWN_REGISTERED = {
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

# 真实点位人数（站点→实际人数，基于计薪表确认后填写）
# 真实人数影响人力成本和补贴金额计算
ACTUAL_STAFF = {
    '分段履约广州万科欧泊': 3,         # 林思敏/卢椅群/黄晓林
    '分段履约广州中大附属第六医院': 6,   # 陈贤乡/谢佳俊/雷文新/詹佳龙/简双玲/谭运亮
    '分段履约广州中大附三岭南医院': 3,   # 林佳宁/黄慧源/张炳英
    '分段履约广州金鹰大厦': 3,          # 蔡嘉成/蓝乐/娜娜
    '分段履约广州汇德国际': 3,          # 钟文轩/蔡文/黄沐芸
    '分段履约广州万菱广场': 2,          # 廖燕锋/胡文轩 (+吴恒志临时)
    '分段履约广州华林国际C馆': 2,       # 黄丹/曾中怡
    '分段履约广州和业广场': 3,          # 张子慧/吴子俏/庄志荣
    '分段履约广州交易广场': 1,          # 新站点 7/3起
}

# 日期特定真实人数覆盖（按日调整，优先级高于 ACTUAL_STAFF）
# 薪资标准: 90元=3h×30, 60元=2h×30, 45元=1.5h×30
ACTUAL_STAFF_OVERRIDES = {
    # ── 万科欧泊 (6/7-6/21, 2-3人/天) ──
    '2026-06-07': {'分段履约广州万科欧泊': 2},   # 周日 林思敏/卢椅群
    '2026-06-08': {'分段履约广州万科欧泊': 2},   # 周一 林思敏/卢椅群
    # 6/9-6/11: 3人 (黄晓林/林思敏/卢椅群) = ACTUAL_STAFF默认
    '2026-06-12': {'分段履约广州万科欧泊': 3},   # 黄晓林/林思敏/黄绍标(替卢)
    '2026-06-14': {'分段履约广州万科欧泊': 3},   # 黄晓林/卢椅群/钟嘉惠(替林)
    # 6/15-6/19: 3人
    '2026-06-20': {'分段履约广州万科欧泊': 3},   # 黄晓林/林思敏/黄绍标

    # ── 中大附属第六医院 (6/17起, 3→5→6人) ──
    '2026-06-17': {
        '分段履约广州中大附属第六医院': 3,  # 陈贤乡/谢佳俊/雷文新
    },
    '2026-06-18': {
        '分段履约广州中大附属第六医院': 5,  # +詹佳龙/简双玲(各2h)
    },
    # 6/19-6/21: 6人 (+谭运亮)

    # ── 中大附三岭南医院 (6/18起) ──
    '2026-06-18': {
        '分段履约广州中大附三岭南医院': 2,  # 林佳宁/黄慧源
    },
    '2026-06-21': {
        '分段履约广州中大附三岭南医院': 2,  # 黄慧源/张炳英
    },

    # ── 金鹰大厦 (6/15-6/18, 工作日3人; 6/19端午0人) ──
    '2026-06-19': {
        '分段履约广州金鹰大厦': 0,
        '分段履约广州汇德国际': 0,
        '分段履约广州万菱广场': 0,
        '分段履约广州华林国际C馆': 0,
        '分段履约广州和业广场': 0,
    },

    # ── 汇德国际 (6/15-6/18, 工作日3人; 6/19端午0人) ──

    # ── 万菱广场 (6/16: +吴恒志临时→3人) ──
    # ── 华林国际C馆 (6/15: 仅黄丹1人) ──
    # ── 和业广场 (6/15-6/16: 仅张子慧/吴子俏2人) ──
    '2026-06-15': {
        '分段履约广州华林国际C馆': 1,
        '分段履约广州和业广场': 2,
    },
    '2026-06-16': {
        '分段履约广州万菱广场': 3,
        '分段履约广州和业广场': 2,
    },
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
MATERIAL_PER_STATION = 0       # 物料摊销 元/天/站 (暂不计入, 待确认口径)
SUBSIDY_PER_EXTRA = 80     # 补贴 (T-1)x80 元/天
PER_PERSON_THRESHOLD = 20  # 补贴门槛 人均单量

# 每日实际人工成本（基于计薪表，优先于 人数×工时×时薪 公式）
# 格式: {"YYYY-MM-DD": {站点全名: 总薪资}}
DAILY_LABOR_COST = {
    # ── 万科欧泊 (90=3h×30) ──
    '2026-06-07': {'分段履约广州万科欧泊': 180},
    '2026-06-08': {'分段履约广州万科欧泊': 180},
    '2026-06-09': {'分段履约广州万科欧泊': 270},
    '2026-06-10': {'分段履约广州万科欧泊': 270},
    '2026-06-11': {'分段履约广州万科欧泊': 270},
    '2026-06-12': {'分段履约广州万科欧泊': 270},
    '2026-06-13': {'分段履约广州万科欧泊': 270},
    '2026-06-14': {'分段履约广州万科欧泊': 270},
    '2026-06-15': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州金鹰大厦': 240, '分段履约广州汇德国际': 180,
        '分段履约广州万菱广场': 180,
        '分段履约广州华林国际C馆': 90,
        '分段履约广州和业广场': 180,
    },
    '2026-06-16': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州金鹰大厦': 240, '分段履约广州汇德国际': 180,
        '分段履约广州万菱广场': 270,
        '分段履约广州华林国际C馆': 180,
        '分段履约广州和业广场': 180,
    },
    '2026-06-17': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州金鹰大厦': 240, '分段履约广州汇德国际': 180,
        '分段履约广州中大附属第六医院': 270,
        '分段履约广州万菱广场': 180,
        '分段履约广州华林国际C馆': 180,
        '分段履约广州和业广场': 270,
    },
    '2026-06-18': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州金鹰大厦': 240, '分段履约广州汇德国际': 180,
        '分段履约广州中大附属第六医院': 390,
        '分段履约广州中大附三岭南医院': 150,
        '分段履约广州万菱广场': 180,
        '分段履约广州华林国际C馆': 90,
        '分段履约广州和业广场': 270,
    },
    '2026-06-19': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州中大附属第六医院': 450,
        '分段履约广州中大附三岭南医院': 240,
    },
    '2026-06-20': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州中大附属第六医院': 450,
        '分段履约广州中大附三岭南医院': 210,
    },
    '2026-06-21': {
        '分段履约广州万科欧泊': 270,
        '分段履约广州中大附属第六医院': 450,
        '分段履约广州中大附三岭南医院': 150,
    },
    '2026-06-22': {
        '分段履约广州中大附三岭南医院': 225,
    },
}

# ── 从计薪表xlsx动态加载配置（覆盖上方默认值）──
if _load_payroll_config():
    print('  [配置] 已从计薪表xlsx加载人力成本数据')
else:
    print('  [配置] 未找到计薪表xlsx, 使用默认配置')

# 日期特定系统登记人员覆盖（仅记录与基准不同的日期）
# 格式: "YYYY-MM-DD" -> {站点: 人数}
# 06-17: 中大附属第六医院尚未从2人扩到6人
REGISTERED_OVERRIDES = {
    '2026-06-17': {
        '分段履约广州中大附属第六医院': 2,  # 6.18才确认登记人员
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

# 站点历史缓存（避免重复扫描）
_station_histories_cache = None


def get_station_histories():
    """扫描所有日期目录, 构建每个站点的逐日历史 DataFrame。
    返回: {站点全名: DataFrame(columns=[date, orders, done, canc, registered, per, profit, canc_comp])}
    """
    global _station_histories_cache
    if _station_histories_cache is not None:
        return _station_histories_cache

    dates = sorted(
        d for d in os.listdir(BASE_DIR)
        if len(d) == 8 and d[2] == '-' and d[5] == '-'
        and os.path.isdir(os.path.join(BASE_DIR, d))
    )

    station_data = {}  # station → list of daily records

    for dd in dates:
        candidates = glob.glob(os.path.join(BASE_DIR, dd, '*.xls')) + \
                     glob.glob(os.path.join(BASE_DIR, dd, '*.xlsx'))
        if not candidates:
            continue
        # 选最新修改时间的文件（与 find_xls 逻辑一致）
        latest_file = max(candidates, key=os.path.getmtime)
        df = pd.read_excel(latest_file)
        df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()
        date_obj = datetime.strptime(f'20{dd[0:2]}-{dd[3:5]}-{dd[6:8]}', '%Y-%m-%d')
        date_display = date_obj.strftime('%m/%d')
        year_date = date_obj.strftime('%Y-%m-%d')

        rider_cols = [c for c in df.columns
                      if c.startswith('经手骑手') and c != '经手骑手1']

        for s in df['站点名称'].unique():
            if s in COMPETITORS:
                continue
            sdf = df[df['站点名称'] == s]
            s_done = (sdf['物流单状态'] == '已送达').sum()
            s_canc = (sdf['物流单状态'] == '已取消').sum()
            canc_comp = sdf.loc[sdf['物流单状态'] == '已取消', '订单实付'].sum()
            # 人均考核排除第三方平台订单（商家ID=-1，不计入人头指标）
            s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
            cnt = len(sdf)  # 总单量（含取消）

            riders = set()
            for col in rider_cols:
                if col in df.columns:
                    for r in sdf[col].dropna():
                        riders.add(str(r).strip())
            registered = len(riders) or 0
            # 补贴考核：人均用已送达单量算（排除第三方平台订单）
            per = s_kpi_done / registered if registered > 0 else 0
            meets = per >= PER_PERSON_THRESHOLD if registered > 0 else False
            subsidy = (registered - 1) * SUBSIDY_PER_EXTRA if meets else 0

            # 人工成本: 优先实际计薪数据
            payroll_cost = DAILY_LABOR_COST.get(year_date, {}).get(s)
            if payroll_cost is not None:
                labor = payroll_cost
            else:
                hours_per = HOURS_OVERRIDES.get(year_date, {}).get(s,
                            STATION_HOURS.get(s, HOURS_PER_PERSON))
                rate = STATION_LABOR_RATE.get(s, LABOR_RATE)
                labor = registered * hours_per * rate
            profit = cnt * SETTLEMENT_PRICE + subsidy - labor - MATERIAL_PER_STATION - canc_comp

            if s not in station_data:
                station_data[s] = []
            station_data[s].append({
                'date': date_display,
                'date_full': year_date,
                'orders': cnt, 'done': s_done, 'canc': s_canc,
                'registered': registered if registered > 0 else None,
                'per': round(per, 1) if registered > 0 else None,
                'meets': meets,
                'profit': round(profit, 1),
                'canc_comp': round(canc_comp, 1),
            })

    _station_histories_cache = station_data
    return station_data


def make_station_trend(station_name, history, color='#818cf8'):
    """生成站点日走势图: 单量柱 + 净利折线"""
    if not history or len(history) < 2:
        return '<p style="color:#64748b">数据不足（需2天以上）</p>'

    dates = [h['date'] for h in history]
    orders = [h['orders'] for h in history]
    profits = [h['profit'] for h in history]
    registered_counts = [h['registered'] for h in history]
    pers = [h['per'] for h in history]

    # 柱状图: 单量, 颜色按达标/未达标
    bar_colors = ['#34d399' if h['meets'] else '#f87171' for h in history]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=orders, name='日单量',
        marker_color=bar_colors,
        text=orders, textposition='outside',
        textfont=dict(color='#e2e8f0', size=10),
        hovertemplate='%{x}<br>%{y}单<br>系统登记%{customdata}人<br>人均%{customdata2}单/人<extra></extra>',
        customdata=list(zip(
            [f'{r}' if r else '?' for r in registered_counts],
            [f'{p}' if p else '?' for p in pers],
        )),
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=profits, name='日净利',
        mode='lines+markers', yaxis='y2',
        line=dict(color='#fbbf24', width=2.5),
        marker=dict(size=7, color='#fbbf24'),
        text=[f'¥{p:+,.0f}' for p in profits],
        textposition='top center',
        textfont=dict(color='#fcd34d', size=10),
        hovertemplate='%{x}<br>净利 ¥%{y:+,.0f}<extra></extra>',
    ))
    # 盈亏平衡线
    fig.add_hline(y=0, line_dash='dot', line_color='rgba(148,163,184,0.4)', line_width=1, yref='y2')

    fig.update_layout(
        title=f'{station_name} · 日走势',
        height=320, xaxis_tickangle=-30,
        yaxis=dict(title=None, gridcolor='rgba(148,163,184,0.06)'),
        yaxis2=dict(title=None, overlaying='y', side='right', showgrid=False),
        legend=dict(orientation='h', y=1.12, x=0),
        margin=dict(t=50, b=50, l=45, r=50),
        hovermode='x unified',
    )
    return dark_fig(fig).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG)


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


def make_time_hist(sdf, title='接力时长分布', color='#818cf8'):
    mask = sdf['骑手1经手_dt'].notna() & sdf['送达时间_dt'].notna()
    times = sdf.loc[mask, '接力时长_min'].dropna()
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
    registered = int(r['系统登记']) if pd.notna(r['系统登记']) else None
    onsite_confirmed = r.get('真实人数已确认', False)
    onsite_display = int(r['真实人数']) if pd.notna(r['真实人数']) else None
    onsite_calc = onsite_display if onsite_confirmed else registered  # 计算时回退到系统登记

    if r['达标'] == 'Y':
        badge = '<span class="badge badge-green">达标</span>'
        status_note = f'人均{r["人均单量"]}单 (+{abs(r["距20单缺口"]):.1f})'
    elif r['达标'] == 'N':
        badge = '<span class="badge badge-red">未达标</span>'
        status_note = f'人均{r["人均单量"]}单 (差{r["距20单缺口"]:.0f}单)'
    else:
        badge = '<span class="badge badge-gray">登记未知</span>'
        status_note = '登记数据缺失'

    if is_ours and onsite_calc:
        meets_per = r['人均单量'] >= 20 if r['人均单量'] else False
        subsidy_per_day = (registered - 1) * 80 if meets_per else 0  # 补贴始终用系统登记
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
    s_labor = r.get('人工成本', onsite_calc * (r.get('工时', HOURS_PER_PERSON) or HOURS_PER_PERSON) * (r.get('时薪', LABOR_RATE) or LABOR_RATE))
    s_hours = r.get('工时', HOURS_PER_PERSON)
    s_rate = r.get('时薪', LABOR_RATE)
    labor_source = r.get('人工来源', 'formula')
    registered_editable = 'kpi-editable' if is_ours and registered else ''

    # 利润线HTML：未确认时仅隐藏依赖真实人力的项目
    if is_ours and onsite_calc:
        subsidy_html = f'<span>补贴 {"+¥" + str(subsidy_per_day) if subsidy_per_day > 0 else "¥0"}</span>'
        if onsite_confirmed:
            profit_val = orders*2.5 + subsidy_per_day - s_labor - MATERIAL_PER_STATION - canc_comp
            profit_color = '#34d399' if profit_val >= 0 else '#f87171'
            labor_html = f'<span>人力 -¥{s_labor:,.0f}</span>'
            profit_html = f'<span class="profit-net-value" id="profit_net_{tab_id}" style="color:{profit_color}">净利 ¥{profit_val:+,.0f}</span>'
            note_extras = ''
            if labor_source == 'payroll':
                note_extras += '<br><span style="color:#34d399">✓ 人力成本来自实际计薪数据</span>'
            note_extras += '| 补贴条件：人均>=20单 | 公式：(系统登记-1)×80'
        else:
            labor_html = '<span style="color:#64748b">人力 —</span>'
            profit_html = f'<span class="profit-net-value" id="profit_net_{tab_id}" style="color:#64748b">净利 —</span>'
            note_extras = '<br><span style="color:#fbbf24">⚠ 缺少真实人力数据，净利待验证</span>'
            note_extras += '| 补贴条件：人均>=20单 | 公式：(系统登记-1)×80'
    else:
        labor_html = subsidy_html = profit_html = note_extras = ''

    # 真实点位人数显示
    if onsite_confirmed:
        onsite_val_html = f'{onsite_display}人'
        onsite_sub_html = '已确认'
        onsite_color = '#34d399'
    else:
        onsite_val_html = '待确认'
        onsite_sub_html = '暂同系统登记'
        onsite_color = '#64748b'

    return f"""
    <div class="tab-panel" id="tab_{tab_id}" data-station="{short}" data-orders="{orders}" data-done="{r['已完成']}" data-kpi-done="{r['考核单量']}" data-registered="{registered or 0}" data-onsite="{onsite_calc or 0}" data-onsite-confirmed="{1 if onsite_confirmed else 0}" data-ours="{1 if is_ours else 0}" data-canc-comp="{canc_comp or 0}" data-labor="{s_labor}" data-labor-source="{labor_source}" data-hours="{s_hours or HOURS_PER_PERSON}" data-rate="{s_rate or LABOR_RATE}">
        <a href="javascript:switchTab('overview')" class="back-link">&larr; 返回总览</a>
        <div class="kpi-grid">
            {kpi_card('订单量', orders, f"完成率 {r['完成率']}%", '#818cf8')}
            {kpi_card('已完成', r['已完成'], f"已取消 {r['已取消']}", '#34d399')}
            {pickup_html}
            <div class="kpi-card {registered_editable}"{' onclick="editRegistered(&quot;' + tab_id + '&quot;, this)"' if is_ours and registered else ''}>
                <div class="kpi-title">系统登记 {'✎' if is_ours and registered else ''}</div>
                <div class="kpi-value registered-val" style="color:#a78bfa">{registered}人</div>
                <div class="kpi-sub">经手骑手2~N去重</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">真实点位人数</div>
                <div class="kpi-value onsite-val" id="onsite_{tab_id}" style="color:{onsite_color}">{onsite_val_html}</div>
                <div class="kpi-sub" id="onsite_sub_{tab_id}">{onsite_sub_html}</div>
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
                <div class="kpi-sub" id="subsidy_formula_{tab_id}">{f'({registered}-1)×80' if is_ours and registered else 'N/A'}</div>
            </div>
            {kpi_card('平均接力', f"{r['平均接力min']}min" if pd.notna(r['平均接力min']) else 'N/A', f"中位 {r['中位接力min']}min", '#34d399')}
            {kpi_card('接力超30min', r['接力超30min'], f"最长 {r['最长接力min']}min" if pd.notna(r['最长接力min']) else '', '#fb923c')}
        </div>

""" + (f"""
        <div class="profit-line" id="profit_line_{tab_id}">
            <span>结算 ¥{orders * 2.5:,.0f}</span>
            {labor_html}
            {subsidy_html}
            <span>取消赔偿 -¥{int(canc_comp):,}</span>
            {profit_html}
        </div>
""" if is_ours and onsite_calc else '') + f"""
        <div class="note-box" id="note_{tab_id}">
            <strong><span id="badge_{tab_id}">{badge}</span> {short}</strong> | <span id="status_{tab_id}">{status_note}</span>
            {note_extras}
        </div>

        <div class="chart-grid">
            <div class="chart-box">{charts['hourly']}</div>
            <div class="chart-box">{charts['relay_time']}</div>
        </div>

        <div class="section-chart" style="margin-top:16px;">
            <h2>到达→送达时间线</h2>
            {charts['timeline']}
        </div>

        {charts.get('trend', '')}
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
    df['hour'] = df['骑手1经手_dt'].dt.hour.astype('Int64')
    df['arrival_hour'] = df['骑手1经手_dt'].dt.hour.astype('Int64')  # 到达点位时段
    df['delivery_hour'] = df['送达时间_dt'].dt.hour.astype('Int64')   # 送达时段
    mask_done = df['送达时间_dt'].notna()
    # 接力配送时长(主指标): 骑手1到达→送达
    mask_arrival = df['骑手1经手_dt'].notna() & mask_done
    df.loc[mask_arrival, '接力时长_min'] = (
        df.loc[mask_arrival, '送达时间_dt'] - df.loc[mask_arrival, '骑手1经手_dt']
    ).dt.total_seconds() / 60
    # 全段时长(参考): 下单→送达
    df.loc[mask_done, '配送时长_min'] = (
        df.loc[mask_done, '送达时间_dt'] - df.loc[mask_done, '下单时间_dt']
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

    # 应用日期特定系统登记人员覆盖
    registered = KNOWN_REGISTERED.copy()
    if date_str in REGISTERED_OVERRIDES:
        registered.update(REGISTERED_OVERRIDES[date_str])

    # ── 从经手骑手2~N 自动检测各站系统登记人员（二段及以后接力人员）──
    # 系统登记人员 = 数据中实际出现的接力人员数（经手骑手2/3/4/5...）
    # 一段（经手骑手1）是美团骑手，不参与我方计数
    onsite_staff = {}  # 站点 → 真实点位人数（默认=系统登记人员）
    registered_detail = {}  # 站点 → 系统登记骑手名单
    # 自动发现所有"经手骑手"列（排除经手骑手1 = 一段美团骑手）
    rider_cols = [c for c in df.columns
                  if c.startswith('经手骑手') and c != '经手骑手1']
    if not rider_cols:
        rider_cols = ['经手骑手2', '经手骑手3']  # 回退兼容

    for s in df['站点名称'].unique():
        if s in COMPETITORS:
            registered[s] = registered.get(s, 0)
            onsite_staff[s] = None  # 竞争方无真实人数数据
            continue
        sdf = df[df['站点名称'] == s]
        riders = set()
        for col in rider_cols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        detected = len(riders)
        configured = registered.get(s)

        if detected > 0:
            # 用自动检测值作为系统登记人员
            registered[s] = detected
            registered_detail[s] = riders
            if configured and detected != configured:
                names = '、'.join(sorted(riders))
                print(f'  [登记更新] {s.replace("分段履约广州","")}: {configured}→{detected}人 — {names}')
        elif not configured:
            registered[s] = 0
            registered_detail[s] = set()

        # 真实点位人数（仅当 ACTUAL_STAFF 明确配置时才取值，否则None=待确认）
        # 真实点位人数：仅当天有计薪数据或明确覆盖时才确认
        act_cfg = ACTUAL_STAFF_OVERRIDES.get(date_str, {})
        payroll = DAILY_LABOR_COST.get(date_str, {})
        if s in act_cfg:
            onsite_staff[s] = act_cfg[s]
        elif s in payroll:
            # 有当天计薪数据 → 从 ACTUAL_STAFF 取人数(匹配计薪期)
            onsite_staff[s] = ACTUAL_STAFF.get(s)
        else:
            onsite_staff[s] = None  # 当天无数据 → 待确认

    # 分类
    df['归属'] = df['站点名称'].apply(lambda s: '竞争方' if s in COMPETITORS else '我方')

    # 全局汇总
    total = len(df)
    ours = df[df['归属'] == '我方']
    comps = df[df['归属'] == '竞争方']
    done = (df['物流单状态'] == '已送达').sum()
    canc = (df['物流单状态'] == '已取消').sum()
    pickup = (df['物流单状态'] == '已取货').sum()
    avg_time = df.loc[mask_arrival, '接力时长_min'].mean()
    median_time = df.loc[mask_arrival, '接力时长_min'].median()
    peak_h = df['hour'].value_counts().idxmax()
    peak_cnt = df['hour'].value_counts().max()

    # 站点汇总
    station_rows = []
    for s in df['站点名称'].unique():
        sdf = df[df['站点名称'] == s]
        s_done = (sdf['物流单状态'] == '已送达').sum()
        s_canc = (sdf['物流单状态'] == '已取消').sum()
        s_pickup = (sdf['物流单状态'] == '已取货').sum()
        # 人均考核排除第三方平台订单（商家ID=-1，不计入人头指标）
        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        cnt = len(sdf)  # 总单量（含取消）
        grp = sdf['归属'].iloc[0]
        reg_count = registered.get(s)           # 系统登记人员
        ons_raw = onsite_staff.get(s)            # 真实点位人数（None=待确认）
        ons_count = ons_raw if ons_raw is not None else reg_count  # 计算时回退到系统登记
        per_person = s_kpi_done / reg_count if reg_count else None  # 人均用已送达单量算（排除第三方平台订单）

        if reg_count and per_person:
            gap = 20 - per_person
            meets = per_person >= 20
            gap_label = f'达标 (+{(-gap):.0f}单)' if meets else f'还差 {gap:.0f} 单'
        else:
            gap = None; meets = False
            gap_label = '登记未知' if reg_count is None else '?'

        s_times = sdf.loc[mask_arrival, '接力时长_min']  # 接力时长为主指标
        # 取消赔偿: 已取消订单的实付金额合计
        canc_mask = sdf['物流单状态'] == '已取消'
        canc_comp = sdf.loc[canc_mask, '订单实付'].sum() if canc_mask.any() else 0
        owner = STATION_OWNER.get(s, '竞争方' if grp == '竞争方' else '')
        # 人工成本: 优先用计薪表实际数据, 否则回退到 人数×工时×时薪
        payroll_cost = DAILY_LABOR_COST.get(date_str, {}).get(s)
        if payroll_cost is not None:
            labor_cost = payroll_cost
            labor_source = 'payroll'  # 实际计薪数据
            s_hours = None  # 无固定工时
            s_rate = 30     # 仅作参考
        else:
            s_hours = HOURS_OVERRIDES.get(date_str, {}).get(s,
                      STATION_HOURS.get(s, HOURS_PER_PERSON))
            s_rate = STATION_LABOR_RATE.get(s, LABOR_RATE)
            labor_cost = ons_count * s_hours * s_rate
            labor_source = 'formula'  # 公式估算
        station_rows.append({
            '站点': s.replace('分段履约广州', ''),
            '全名': s, '归属': grp,
            '订单量': cnt, '已完成': s_done, '考核单量': s_kpi_done, '已取消': s_canc, '取消赔偿': canc_comp,
            '已取货': s_pickup,
            '完成率': round(s_done / cnt * 100, 1) if cnt else 0,
            '系统登记': reg_count,
            '真实人数': ons_count,
            '真实人数已确认': ons_raw is not None,
            '人均单量': round(per_person, 1) if per_person else None,
            '距20单缺口': gap,
            '达标': 'Y' if meets else ('N' if reg_count else '?'),
            '缺口描述': gap_label,
            '归属人': owner,
            '人工成本': labor_cost,
            '人工来源': labor_source,
            '工时': s_hours,
            '时薪': s_rate,
            '平均接力min': round(s_times.mean(), 1) if len(s_times) > 0 else None,
            '中位接力min': round(s_times.median(), 1) if len(s_times) > 0 else None,
            '接力超30min': int((s_times > 30).sum()),
            '最长接力min': round(s_times.max(), 1) if len(s_times) > 0 else None,
        })

    st = pd.DataFrame(station_rows).sort_values('订单量', ascending=False)
    st_ours = st[st['归属'] == '我方']
    st_comps = st[st['归属'] == '竞争方']

    # rider_check 已在上方自动检测中完成（onsite_staff / registered_detail）

    # ── 图表 ──
    known = st_ours[st_ours['系统登记'].notna()].copy().sort_values('人均单量')
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

    times_all = df.loc[mask_arrival, '接力时长_min'].dropna()
    fig_time_all = go.Figure()
    fig_time_all.add_trace(go.Histogram(
        x=times_all, nbinsx=30, marker_color='#34d399',
        hovertemplate='%{x:.0f}min: %{y}单<extra></extra>'
    ))
    for pct, clr, label in [(50, '#34d399', '中位'), (90, '#f87171', 'P90')]:
        val = np.percentile(times_all, pct)
        fig_time_all.add_vline(x=val, line_dash='dash', line_color=clr,
                               annotation_text=f'{label} {val:.0f}min', annotation_position='top',
                               annotation_font_color=clr)
    fig_time_all.update_layout(
        title=f'全站接力时长分布（均值{times_all.mean():.0f}min · 骑手到达→送达 · n={len(times_all)}）',
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
        # 站点日走势图
        trend_html = ''
        if row['归属'] == '我方':
            histories = get_station_histories()
            if full_name in histories and len(histories[full_name]) >= 2:
                trend_chart = make_station_trend(short, histories[full_name], color)
                trend_html = ('\n        <div class="section-chart" style="margin-top:16px;">\n'
                              + trend_chart +
                              '\n        </div>')

        station_charts[full_name] = {
            'hourly': make_hourly_chart(sdf, f'{short} · 分时订单量', color),
            'relay_time': make_time_hist(sdf, f'{short} · 接力时长分布', color),
            'timeline': make_dual_timeline(sdf, timeline_title),
            'trend': trend_html,
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
        reg_s = f'{int(r["系统登记"])}人' if pd.notna(r['系统登记']) else '?'
        if r.get('真实人数已确认'):
            ons_s = f'{int(r["真实人数"])}人'
        else:
            ons_s = '<span style="color:#64748b">待确认</span>'
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
        <td>{reg_s}</td>
        <td>{ons_s}</td>
        <td>{owner}</td>
        <td>{per_s}</td>
        <td><b style="color:{gap_color}">{gap_s}{pickup_s}</b></td>
        <td>{badge}</td>
        <td>{r['平均接力min']}min</td>
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
            <button class="export-btn" id="exportRegisteredBtn" onclick="exportRegisteredConfig()" style="display:none;float:right;">导出登记配置</button>
        </div>

        <div class="kpi-grid">
            {kpi_card('我方订单', f'{len(ours)}单', f'{len(st_ours)}站', '#818cf8')}
            {kpi_card('竞争方订单', f'{len(comps)}单', f'{len(st_comps)}站', '#f87171')}
            {kpi_card('已完成', f'{done_pct:.1f}%', f'{done}已送达 / {canc}取消', '#34d399')}
            {kpi_card('配送中', pickup, '已取货未送达', '#fbbf24')}
            {kpi_card('平均接力时长', f'{avg_time:.0f}min', f'中位 {median_time:.0f}min', '#34d399')}
            {kpi_card('峰值', f'{peak_cnt}单', f'{int(peak_h):02d}:00时段', '#f472b6')}
            {kpi_card('接力超30min', int((df['接力时长_min'] > 30).sum()), f'占比 {(df["接力时长_min"] > 30).sum()/mask_arrival.sum()*100:.1f}%' if mask_arrival.sum() > 0 else '', '#fb923c')}
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
                    <th>站点</th><th>订单量</th><th>完成率</th><th>系统登记</th><th>真实人数</th><th>归属人</th>
                    <th>人均单量</th><th>距20单门槛</th><th>达标</th>
                    <th>平均接力</th><th>已取消</th><th>取消赔偿</th>
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
    <div class="meta">{date_display} &nbsp;·&nbsp; 我方 {len(ours)}单/{len(st_ours)}站 &nbsp;|&nbsp; 竞争方 {len(comps)}单/{len(st_comps)}站 &nbsp;·&nbsp; {t_min.strftime('%H:%M')}-{t_max.strftime('%H:%M')} &nbsp;·&nbsp; {now_str} 更新 &nbsp;·&nbsp; <span style="color:{coverage_color}">{coverage_label}</span></div>
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

var registeredChanges = {{}};  // {{tabId: newRegistered}}

function editRegistered(tabId, card) {{
    var valEl = card.querySelector('.registered-val');
    var current = parseInt(valEl.textContent);
    var input = prompt('修改系统登记人数 (当前 '+current+'人):', current);
    if (input === null || input === '') return;
    var newReg = parseInt(input);
    if (isNaN(newReg) || newReg < 1) return;
    valEl.textContent = newReg + '人';
    registeredChanges[tabId] = newReg;
    recalcUE(tabId, newReg);
    updateExportBtn();
}}

function recalcUE(tabId, registered) {{
    var panel = document.getElementById('tab_' + tabId);
    var orders = parseInt(panel.dataset.orders);
    var done = parseInt(panel.dataset.done) || 0;
    var kpiDone = parseInt(panel.dataset.kpiDone) || 0;
    var perPerson = (kpiDone / registered).toFixed(1);  // 补贴考核用已送达单量（排除第三方平台订单）
    var meets = perPerson >= 20;
    // 真实人数：已确认则保持，否则回退到系统登记用于计算
    var onsiteConfirmed = parseInt(panel.dataset.onsiteConfirmed) || 0;
    var onsite = onsiteConfirmed ? parseInt(panel.dataset.onsite) : registered;
    var subsidy = meets ? (registered - 1) * 80 : 0;  // 补贴始终用系统登记

    // 更新真实点位人数显示
    var onsEl = document.getElementById('onsite_' + tabId);
    var onsSub = document.getElementById('onsite_sub_' + tabId);
    if (onsEl) {{
        if (onsiteConfirmed) {{
            onsEl.textContent = onsite + '人';
            onsEl.style.color = '#34d399';
        }} else {{
            onsEl.textContent = '待确认';
            onsEl.style.color = '#64748b';
        }}
    }}
    if (onsSub) {{
        onsSub.textContent = onsiteConfirmed ? '已确认' : '暂同系统登记';
    }}

    // 人均单量（用系统登记算）
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

    // 补贴（用真实人数算金额）
    var subEl = document.getElementById('subsidy_' + tabId);
    var subForm = document.getElementById('subsidy_formula_' + tabId);
    if (subEl) {{
        subEl.textContent = subsidy + '元';
        subEl.style.color = subsidy > 0 ? '#34d399' : '#f87171';
    }}
    if (subForm) subForm.textContent = '(' + registered + '-1)x80';

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

    // 盈利重算（人力成本: 有实际数据则用之, 否则公式估算）
    var settlement = orders * 2.5;
    var laborSource = panel.dataset.laborSource || 'formula';
    var labor;
    if (laborSource === 'payroll') {{
        labor = parseInt(panel.dataset.labor) || 0;
    }} else {{
        var hours = parseFloat(panel.dataset.hours) || 3;
        var rate = parseFloat(panel.dataset.rate) || 30;
        labor = onsite * hours * rate;
    }}
    var material = 100/30;
    var cancComp = parseFloat(panel.dataset.cancComp) || 0;
    var lineSubsidy = meets ? (onsite - 1) * 80 : 0;
    var profit = settlement + lineSubsidy - labor - material - cancComp;
    // 未确认时加 * 标注
    var asterisk = onsiteConfirmed ? '' : '<sup style="color:#64748b">*</sup>';
    var profitLine = document.getElementById('profit_line_' + tabId);
    if (profitLine) {{
        var spans = profitLine.querySelectorAll('span');
        if (spans.length >= 5) {{
            spans[0].innerHTML = '结算 ¥' + settlement.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[1].innerHTML = '人力 -¥' + labor.toLocaleString('en', {{maximumFractionDigits:0}}) + asterisk;
            spans[2].innerHTML = '补贴 ' + (lineSubsidy > 0 ? '+¥' + lineSubsidy : '0') + asterisk;
            spans[3].innerHTML = '取消赔偿 -¥' + cancComp.toLocaleString('en', {{maximumFractionDigits:0}});
            spans[4].innerHTML = '净利 ¥' + (profit >= 0 ? '+' : '') + profit.toLocaleString('en', {{maximumFractionDigits:0}}) + asterisk;
            spans[4].style.color = profit >= 0 ? '#34d399' : '#f87171';
        }}
    }}

    // 存储
    localStorage.setItem('registered_overrides_' + window.location.pathname, JSON.stringify(registeredChanges));
}}

function updateExportBtn() {{
    var btn = document.getElementById('exportRegisteredBtn');
    if (btn) btn.style.display = Object.keys(registeredChanges).length ? 'inline-block' : 'none';
}}

// Load saved overrides on page load
document.addEventListener('DOMContentLoaded', function() {{
    var saved = localStorage.getItem('registered_overrides_' + window.location.pathname);
    if (saved) {{
        registeredChanges = JSON.parse(saved);
        Object.keys(registeredChanges).forEach(function(tabId) {{
            var card = document.querySelector('#tab_' + tabId + ' .kpi-editable');
            if (card) {{
                var newReg = registeredChanges[tabId];
                card.querySelector('.registered-val').textContent = newReg + '人';
                recalcUE(tabId, newReg);
            }}
        }});
    }}
    updateExportBtn();
}});

function exportRegisteredConfig() {{
    var lines = [];
    Object.keys(registeredChanges).forEach(function(tabId) {{
        var panel = document.getElementById('tab_' + tabId);
        var station = panel.dataset.station;
        lines.push("        '分段履约广州" + station + "': " + registeredChanges[tabId] + ",");
    }});
    if (!lines.length) {{ alert('暂无修改'); return; }}
    var code = "'" + document.title.split('|')[1].trim() + "': {{\\n" + lines.join('\\n') + "\\n    }},";
    navigator.clipboard.writeText(code).then(function() {{
        alert('已复制到剪贴板:\\n\\n' + code + '\\n\\n粘贴到 build_dashboard.py 的 REGISTERED_OVERRIDES 中');
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
    day_confirmed_count = 0  # 有确认数据的站点数
    for _, r in st.iterrows():
        cnt = r['订单量']
        grp = r['归属']
        reg_count = r['系统登记']
        ons_count = r['真实人数']
        ons_confirmed = r.get('真实人数已确认', False)
        per_p = r['人均单量'] if pd.notna(r['人均单量']) else None

        if grp == '我方' and reg_count and cnt > 0:
            settlement = cnt * SETTLEMENT_PRICE
            canc_comp = r['取消赔偿']

            # 补贴始终基于系统登记计算
            meets = per_p and per_p >= PER_PERSON_THRESHOLD
            subsidy = (reg_count - 1) * SUBSIDY_PER_EXTRA if meets else 0

            # 结算/补贴/赔偿始终计入（基于客观数据）
            day_total_revenue += settlement
            day_total_subsidy += subsidy
            day_total_canc_comp += canc_comp

            if ons_confirmed:
                day_confirmed_count += 1
                labor = r['人工成本']
                profit = settlement + subsidy - labor - MATERIAL_PER_STATION - canc_comp
                labor_disp = round(labor, 1)
                subsidy_disp = round(subsidy, 1)
                profit_disp = round(profit, 1)
                day_total_labor += labor
            else:
                labor_disp = None      # 人力待确认
                subsidy_disp = round(subsidy, 1)  # 补贴照常(基于系统登记)
                profit_disp = None     # 净利待确认(缺人力成本)

            station_profits.append({
                '站点': r['站点'],
                '归属': grp,
                '订单量': cnt,
                '已完成': r['已完成'],
                '系统登记': reg_count,
                '真实人数': ons_count,
                '真实人数已确认': ons_confirmed,
                '人均单量': per_p,
                '已取消': r['已取消'],
                '取消赔偿': round(canc_comp, 1),
                '结算收入': round(settlement, 1),
                '人力成本': labor_disp,
                '物料': round(MATERIAL_PER_STATION, 1),
                '补贴': subsidy_disp,
                '净利': profit_disp,
                '达标': r['达标'],
            })

    # 检查是否有未确认真实人数的站点
    any_unconfirmed = any(not sp.get('真实人数已确认', False) for sp in station_profits)

    # 日净利：有未确认站点时整体不可靠，显示占位符
    if any_unconfirmed:
        day_profit = None
    elif day_confirmed_count > 0:
        day_profit = round(day_total_revenue + day_total_subsidy - day_total_labor - day_total_material - day_total_canc_comp, 1)
    else:
        day_profit = None

    # ── 生成单日 UE 分析页 ──
    build_ue_page(date_display, total, len(st_ours), station_profits,
                  day_profit, day_total_revenue, day_total_subsidy, day_total_labor,
                  day_total_canc_comp, any_unconfirmed, t_min, t_max)

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
        'any_unconfirmed': any(not sp.get('真实人数已确认', False) for sp in station_profits),
    }


def build_ue_page(date_display, total_orders, ours_count, station_profits,
                  day_profit, day_revenue, day_subsidy, day_labor,
                  day_canc_comp, any_unconfirmed, t_min, t_max):
    """生成单日 UE 盈利分析页面 MMDD_ue.html"""
    date_obj = datetime.strptime(date_display, '%Y-%m-%d')
    mdd = date_obj.strftime('%m%d')
    date_short = date_obj.strftime('%y-%m-%d')
    ue_path = os.path.join(BASE_DIR, f'{mdd}_ue.html')
    date_dir = os.path.join(BASE_DIR, date_short)
    ue_dir_path = os.path.join(date_dir, 'ue_analysis.html')

    profit_color = '#34d399' if (day_profit or 0) >= 0 else '#f87171'
    day_material = ours_count * MATERIAL_PER_STATION

    # ── KPI 卡片 ──
    profit_rate = (day_profit / day_revenue * 100) if day_revenue > 0 and day_profit is not None else None

    # ── 站点净利排名图 ──
    sp_confirmed = [sp for sp in station_profits if sp['净利'] is not None]
    sp_sorted = sorted(sp_confirmed, key=lambda x: x['净利']) if sp_confirmed else []
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

    # 成本构成: 人力 vs 取消赔偿
    fig_cost = go.Figure()
    fig_cost.add_trace(go.Pie(
        labels=['人力成本', '取消赔偿'],
        values=[day_labor, day_canc_comp],
        marker_colors=['#f87171', '#ef4444'],
        hole=0.5, textinfo='label+value',
        textfont=dict(color='#e2e8f0', size=11),
    ))
    fig_cost.update_layout(title='成本构成', height=280, showlegend=False,
                           margin=dict(t=45, b=10, l=10, r=10))
    html_cost = dark_fig(fig_cost).to_html(full_html=False, include_plotlyjs=False, config=PLOTLY_CONFIG, div_id='chart_cost')

    # ── 站点明细表 ──
    rows = ''
    for sp in sorted(station_profits, key=lambda x: (x['净利'] is not None, x['净利'] or 0), reverse=True):
        pc = '#34d399' if (sp['净利'] or 0) >= 0 else '#f87171'
        subsidy_str = f'+{sp["补贴"]:.0f}' if (sp['补贴'] or 0) > 0 else '0'
        canc_str = f'{sp.get("已取消",0)}单' if sp.get('已取消', 0) > 0 else '0'
        comp_str = f'-¥{sp.get("取消赔偿",0):.0f}' if sp.get('取消赔偿', 0) > 0 else '0'
        ons_display = f'{sp["真实人数"]}人' if sp.get('真实人数已确认') else '<span style="color:#64748b">待确认</span>'
        labor_str = f'-¥{sp["人力成本"]:,.0f}' if sp['人力成本'] is not None else '<span style="color:#64748b">—</span>'
        sub_str = subsidy_str  # 补贴始终基于系统登记，不受真实人力影响
        profit_str = f'¥{sp["净利"]:+,.0f}' if sp['净利'] is not None else '<span style="color:#64748b">—</span>'
        rows += f"""
                <tr>
                  <td>{sp['站点']}</td>
                  <td>{sp['订单量']}</td>
                  <td>{canc_str}</td>
                  <td>{sp['系统登记']}人</td>
                  <td>{ons_display}</td>
                  <td>{sp['人均单量']}单/人</td>
                  <td>¥{sp['结算收入']:,.0f}</td>
                  <td>{labor_str}</td>
                  <td style="color:#f87171">{comp_str}</td>
                  <td>{sub_str}</td>
                  <td style="color:{pc};font-weight:600">{profit_str}</td>
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
        <strong>UE 参数</strong> &nbsp;结算 {SETTLEMENT_PRICE}元/单 &nbsp;|&nbsp; 人力 {LABOR_RATE}元/h×{HOURS_PER_PERSON}h &nbsp;|&nbsp; 补贴 (T-1)×{SUBSIDY_PER_EXTRA}元 &nbsp;|&nbsp; 门槛≥{PER_PERSON_THRESHOLD}单/人
    </div>
""" + (f"""
    <div class="note-box" style="border-left-color:#fbbf24;background:rgba(251,191,36,0.06);">
        <strong style="color:#fbbf24">⚠ 人力成本待确认</strong> &nbsp;所有站点真实点位人数尚未确认，当前人力成本基于系统登记人数估算，净利仅供参考。
    </div>
""" if any_unconfirmed else '') + f"""

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">总收入</div>
            <div class="kpi-value" style="color:#818cf8">¥{day_revenue:,.0f}</div>
            <div class="kpi-sub">结算收入 2.5元/单</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">总人力成本{'<sup style="color:#64748b;font-size:10px">*</sup>' if any_unconfirmed else ''}</div>
            <div class="kpi-value" style="color:#f87171">-¥{day_labor:,.0f}</div>
            <div class="kpi-sub">{ours_count}站 × 人均{LABOR_RATE}元/h×{HOURS_PER_PERSON}h</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">取消赔偿</div>
            <div class="kpi-value" style="color:#f87171">-¥{day_canc_comp:,.0f}</div>
            <div class="kpi-sub">已取消订单实付金额</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">总补贴{'<sup style="color:#64748b;font-size:10px">*</sup>' if any_unconfirmed else ''}</div>
            <div class="kpi-value" style="color:#fbbf24">+¥{day_subsidy:,.0f}</div>
            <div class="kpi-sub">(T-1)×{SUBSIDY_PER_EXTRA}元</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">日净利{'<sup style="color:#64748b;font-size:10px">*</sup>' if any_unconfirmed else ''}</div>
            <div class="kpi-value" style="color:{profit_color}">{('¥' + f'{day_profit:+,.0f}') if day_profit is not None else '<span style="font-size:18px;color:#64748b">—</span>'}</div>
            <div class="kpi-sub">{('利润率 ' + f'{profit_rate:+.1f}%') if profit_rate is not None else '部分站点未验证'}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">单均净利{'<sup style="color:#64748b;font-size:10px">*</sup>' if any_unconfirmed else ''}</div>
            <div class="kpi-value" style="color:{profit_color}">{('¥' + f'{(day_profit/total_orders):+.2f}') if day_profit is not None else '<span style="font-size:18px;color:#64748b">—</span>'}</div>
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
                <th>站点</th><th>单量</th><th>取消</th><th>系统登记</th><th>真实人数</th><th>人均</th>
                <th>结算</th><th>人力</th><th>赔偿</th><th>补贴</th><th>净利</th>
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


def save_summary_cache(summaries, path='_summary_cache.json'):
    """将日期摘要存入缓存文件"""
    import json
    cache = {}
    for s in summaries:
        cache[s['date']] = serialize_summary(s)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, default=str)


def load_summary_cache(path='_summary_cache.json'):
    """读取缓存的日期摘要"""
    import json
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    cache = {}
    for date_str, data in raw.items():
        cache[date_str] = deserialize_summary(data)
    return cache


def serialize_summary(s):
    """把 summary dict 转为 JSON-safe dict"""
    out = {}
    for k, v in s.items():
        if k == 'station_profits':
            out[k] = [{sk: sv for sk, sv in sp.items()} for sp in v]
        else:
            out[k] = v
    return out


def deserialize_summary(data):
    """从 JSON-safe dict 还原 summary"""
    return data


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

    # ── 站点累计汇总 ──
    # 聚合所有日期的 station_profits
    station_cum = {}  # {站点名: {orders, done, canc, days, profit, revenue, subsidy, labor, canc_comp}}
    for d in dates_summary:
        for sp in d.get('station_profits', []):
            sn = sp['站点']
            if sn not in station_cum:
                station_cum[sn] = {'orders': 0, 'done': 0, 'canc': 0, 'days': 0, 'profit': 0.0,
                                   'revenue': 0.0, 'subsidy': 0.0, 'labor': 0.0, 'canc_comp': 0.0,
                                   'registered': sp.get('系统登记', 0),
                                   'onsite': sp.get('真实人数', 0),
                                   'onsite_confirmed': sp.get('真实人数已确认', False)}
            station_cum[sn]['orders'] += sp['订单量']
            station_cum[sn]['done'] += sp.get('已完成', 0)  # 已完成=已送达; 订单量已排除取消, 直接取已完成字段
            station_cum[sn]['canc'] += sp.get('已取消', 0)
            station_cum[sn]['days'] += 1
            station_cum[sn]['profit'] += (sp.get('净利') or 0)
            station_cum[sn]['revenue'] += sp.get('结算收入', 0)
            station_cum[sn]['subsidy'] += (sp.get('补贴') or 0)
            station_cum[sn]['labor'] += (sp.get('人力成本') or 0)
            station_cum[sn]['canc_comp'] += (sp.get('取消赔偿') or 0)

    # ── 最新一天各站点横比表 ──
    latest_summary = dates_summary[0]
    latest_profits = latest_summary.get('station_profits', [])
    # Sort by orders descending
    latest_profits_sorted = sorted(latest_profits, key=lambda x: x['订单量'], reverse=True)

    compare_rows = ''
    for sp in latest_profits_sorted:
        conf = sp.get('真实人数已确认', False)
        orders = sp['订单量']
        reg = sp['系统登记']
        onsite = sp['真实人数']
        per = sp['人均单量']
        completed = sp.get('已完成', orders - sp.get('已取消', 0))
        done_pct = completed / orders * 100 if orders > 0 else 0
        relay_str = '—'

        # 达标判断
        if per and per >= 20:
            badge = '<span class="badge badge-green">达标</span>'
            gap_str = f'+{per-20:.0f}'
        elif per:
            badge = '<span class="badge badge-red">未达标</span>'
            gap_str = f'-{20-per:.0f}'
        else:
            badge = '<span class="badge badge-gray">?</span>'
            gap_str = '?'

        onsite_str = f'{onsite}人' if conf else '<span style="color:#64748b">待确认</span>'
        labor_str = f'-¥{sp["人力成本"]:,.0f}' if sp['人力成本'] is not None else '<span style="color:#64748b">—</span>'
        profit_str = f'¥{sp["净利"]:+,.0f}' if sp['净利'] is not None else '<span style="color:#64748b">—</span>'
        subsidy_str = f'+¥{sp["补贴"]:.0f}' if sp['补贴'] > 0 else '¥0'
        comp_str = f'-¥{sp.get("取消赔偿",0):,.0f}' if sp.get('取消赔偿', 0) > 0 else '¥0'
        pc = '#34d399' if (sp['净利'] or 0) >= 0 else '#f87171'

        compare_rows += f"""
              <tr>
                <td style="color:var(--text);font-weight:500">{sp['站点']}</td>
                <td style="color:#818cf8;font-weight:600">{orders}</td>
                <td style="color:var(--text-dim)">{done_pct:.0f}%</td>
                <td style="color:#a78bfa">{reg}人</td>
                <td style="color:{('#34d399' if conf else '#64748b')}">{onsite_str}</td>
                <td style="color:var(--text-dim)">{per}单/人</td>
                <td><b style="color:{'#34d399' if per and per>=20 else '#f87171'}">{gap_str}</b></td>
                <td>{badge}</td>
                <td style="color:#34d399">¥{sp['结算收入']:,.0f}</td>
                <td style="color:{('#f87171' if conf else '#64748b')}">{labor_str}</td>
                <td style="color:#fbbf24">{subsidy_str}</td>
                <td style="color:#f87171">{comp_str}</td>
                <td style="color:{pc};font-weight:700">{profit_str}</td>
              </tr>"""

    compare_table_html = f"""
      <div class="section-chart" style="margin-bottom:20px;">
        <h2>📊 最新一天 · 各站点横比（{latest_summary['date']}）</h2>
        <div style="max-height:500px;overflow:auto;">
        <table>
          <thead><tr>
            <th>站点</th><th>单量</th><th>完成率</th><th>登记</th><th>真实人数</th>
            <th>人均</th><th>距20</th><th>达标</th>
            <th>结算</th><th>人力</th><th>补贴</th><th>赔偿</th><th>净利</th>
          </tr></thead>
          <tbody>{compare_rows}</tbody>
        </table>
        </div>
      </div>"""

    # ── 站点累计汇总（下移到日期卡片之后）──
    cum_sorted = sorted(station_cum.items(), key=lambda x: x[1]['orders'], reverse=True)

    cum_rows = ''
    for sn, sc in cum_sorted:
        confirmed = sc['onsite_confirmed']
        subsidy_str = f'+¥{sc["subsidy"]:,.0f}' if sc['subsidy'] > 0 else '¥0'  # 补贴始终基于系统登记
        if confirmed:
            pc = '#34d399' if sc['profit'] >= 0 else '#f87171'
            labor_str = f'-¥{sc["labor"]:,.0f}'
            profit_str = f'¥{sc["profit"]:+,.0f}'
            onsite_str = f'{sc["onsite"]}人'
        else:
            pc = '#64748b'
            labor_str = '<span style="color:#64748b">—</span>'
            profit_str = '<span style="color:#64748b">—</span>'
            onsite_str = '<span style="color:#64748b">待确认</span>'
        avg_per_day = sc['orders'] / sc['days'] if sc['days'] > 0 else 0
        cum_rows += f"""
              <tr>
                <td style="color:var(--text);font-weight:500">{sn}</td>
                <td style="color:#818cf8;font-weight:600">{sc['orders']}</td>
                <td style="color:var(--text-dim)">{sc['days']}天</td>
                <td style="color:var(--text-dim)">{avg_per_day:.0f}单/天</td>
                <td style="color:#a78bfa">{sc['registered']}人</td>
                <td style="color:{('#34d399' if confirmed else '#64748b')}">{onsite_str}</td>
                <td style="color:var(--text-dim)">{sc['done']} / <span style="color:#f87171">{sc['canc']}</span></td>
                <td style="color:#34d399">¥{sc['revenue']:,.0f}</td>
                <td style="color:{('#f87171' if confirmed else '#64748b')}">{labor_str}</td>
                <td style="color:{('#fbbf24' if confirmed else '#64748b')}">{subsidy_str}</td>
                <td style="color:#f87171">{'-¥'+format(sc['canc_comp'],',.0f') if sc['canc_comp'] > 0 else '¥0'}</td>
                <td style="color:{pc};font-weight:700">{profit_str}</td>
              </tr>"""

    # Check if any station has unconfirmed headcount
    any_cum_unconfirmed = any(not sc.get('onsite_confirmed', False) for _, sc in station_cum.items())

    cum_table_html = f"""
      <div class="section-chart" style="margin-bottom:20px;">
        <h2>📊 站点累计汇总（{num_dates}天）{"<span style='color:#64748b;font-size:12px;font-weight:400'> — 人力/补贴/净利基于系统登记估算</span>" if any_cum_unconfirmed else ""}</h2>
        <div style="max-height:500px;overflow:auto;">
        <table>
          <thead><tr>
            <th>站点</th><th>累计单量</th><th>天数</th><th>日均</th><th>系统登记</th><th>真实人数</th>
            <th>完成/取消</th><th>累计结算</th><th>累计人力</th><th>累计补贴</th><th>累计赔偿</th><th>累计净利</th>
          </tr></thead>
          <tbody>{cum_rows}</tbody>
        </table>
        </div>
      </div>"""

    # ── 走势图 ──
    trend_data = sorted(dates_summary, key=lambda x: x['date'])
    trend_dates = [f"{int(d['date'][5:7])}/{int(d['date'][8:10])}" for d in trend_data]  # M/D
    trend_orders = [d['total'] for d in trend_data]
    trend_profits = [(d.get('day_profit') or 0) for d in trend_data]
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
        x=trend_dates, y=[-(l + d.get('day_canc_comp', 0)) for l, d in zip(trend_labors, trend_data)],
        name='成本(人力+赔偿)',
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
        profit_color = '#34d399' if (d.get('day_profit') or 0) >= 0 else '#f87171'
        day_unconfirmed = d.get('any_unconfirmed', False)

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
        elif day_unconfirmed:
            profit_row = f"""
        <a href="{mdd}_ue.html" class="profit-summary">
          <span>结算 ¥{d.get('day_revenue',0):,.0f}</span>
          <span style="color:#64748b">人力 —</span>
          <span>赔偿 -¥{d.get('day_canc_comp',0):,.0f}</span>
          <span>补贴 +¥{d.get('day_subsidy',0):,.0f}</span>
          <span class="profit-net" style="color:#64748b">日净利 —</span>
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

.section-chart {{
  background: var(--surface);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 22px; margin-bottom: 16px;
}}
.section-chart h2 {{
  font-size: 15px; font-weight: 700; color: var(--text);
  padding-bottom: 10px; margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 8px;
}}
.section-chart h2::before {{
  content: ''; width: 4px; height: 18px; border-radius: 2px;
  background: var(--accent);
}}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th {{
  background: rgba(30,41,59,0.6); color: var(--text-dim); font-weight: 600;
  padding: 9px 10px; text-align: left; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
}}
td {{
  padding: 7px 10px; border-bottom: 1px solid rgba(148,163,184,0.06);
  color: var(--text-dim);
}}
tr:last-child td {{ border-bottom: none; }}
tr:hover td {{ background: rgba(129,140,248,0.04); }}

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
{compare_table_html}
  <div class="main-layout">
    <div class="main-cards">
{cards_html}
    </div>
{trends_html}
  </div>
{cum_table_html}
  <div class="footer">
    接力送 &middot; 楼宇末端配送运营数据 &nbsp;|&nbsp; 数据来源: 美团校园订单详情导出
  </div>

</div>

</body>
</html>"""

    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f'\n[OK] 总主页已更新: {total_orders:,}单 / {num_dates}天 / {max_stations}站')
    print(f'')
    print(f'  # 推送 + 验证线上部署:')
    print(f'  python scripts/deploy.py 数据更新至{latest_date[-5:]}')


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
    sync_mode = '--sync' in sys.argv
    full_mode = '--full' in sys.argv

    if sync_mode and arg not in ('--all', '--update-index', '--fetch-payroll'):
        print('>>> 读取本地计薪表...')
        print()

    if arg == '--all' or full_mode:
        # 全量模式：重建所有日期
        dates = discover_dates()
        if not dates:
            print('未发现任何日期目录。')
            sys.exit(1)
        print(f'全量重建 {len(dates)} 个日期的看板...\n')
        summaries = []
        for d in dates:
            try:
                s = process_date(d)
                summaries.append(s)
            except Exception as e:
                print(f'  [{d}] 错误: {e}')
        print()
        update_index(summaries)
        save_summary_cache(summaries)
        print(f'[OK] 全量完成，缓存已更新 ({len(summaries)}天)')

    elif arg == '--fetch-payroll':
        print('已废弃: 计薪表改为本地手动维护, 不再从腾讯文档拉取。')
        print(f'请直接编辑: 接力送真实人力计薪/接力送计薪表格.xlsx')

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
        save_summary_cache(summaries)

    else:
        # 增量模式：只处理指定日期，其余从缓存读取
        date_str = arg
        cache = load_summary_cache()

        summary = process_date(date_str)
        summaries = [summary]

        all_dates = discover_dates()
        cached_count = 0
        rebuilt_count = 0
        for d in all_dates:
            if d == date_str:
                continue
            if d in cache:
                summaries.append(cache[d])
                cached_count += 1
            else:
                try:
                    s = process_date(d)
                    summaries.append(s)
                    rebuilt_count += 1
                except Exception as e:
                    print(f'  [{d}] 跳过: {e}')

        line = f'[增量] 处理 1 天'
        if cached_count:
            line += f' + 缓存 {cached_count} 天'
        if rebuilt_count:
            line += f' + 重建 {rebuilt_count} 天'
        line += f' (共 {len(summaries)} 天)'
        print(line)
        update_index(summaries)
        save_summary_cache(summaries)
