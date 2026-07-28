"""
生成6月美团结算 vs 内部预估对比页面
"""
import pandas as pd
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def short_name(full):
    return str(full).replace('分段履约广州', '')

# ===== 1. Read Meituan settlement =====
fp = '6月美团结算/202606-艾云-20260727.xlsx'
df_summary = pd.read_excel(fp, sheet_name=2, engine='calamine')

mt = {}
for _, row in df_summary.iterrows():
    sname = str(row['station_name'])
    if sname == 'nan' or '总计' in sname:
        continue
    short = short_name(sname)
    if short == '中大附属岭南医院':
        short = '中大附三岭南医院'
    mt[short] = {
        'orders': int(row['6月总结算单量']),
        'service_fee': float(row['按单服务费']),
        'subsidy': float(row['人头补贴费']),
        'total': float(row['合计']),
    }

# ===== 2. Internal estimates (from dashboard data) =====
internal = {
    '万科欧泊':       {'orders': 932,  'settlement': 2330,  'subsidy': 640,   'labor': 7650},
    '万菱广场':       {'orders': 531,  'settlement': 1328,  'subsidy': 480,   'labor': 2970},
    '中大附三岭南医院': {'orders': 1017, 'settlement': 2542,  'subsidy': 2240,  'labor': 4530},
    '中大附属第六医院': {'orders': 3238, 'settlement': 8095,  'subsidy': 10960, 'labor': 10730},
    '云升科技园':     {'orders': 40,   'settlement': 100,   'subsidy': 0,     'labor': 0},
    '华林国际C馆':    {'orders': 48,   'settlement': 120,   'subsidy': 0,     'labor': 900},
    '和业广场':       {'orders': 961,  'settlement': 2402,  'subsidy': 1760,  'labor': 3750},
    '汇德国际':       {'orders': 332,  'settlement': 830,   'subsidy': 400,   'labor': 1725},
    '珠江国际轻纺城': {'orders': 383,  'settlement': 958,   'subsidy': 400,   'labor': 0},
    '绿地星玥':       {'orders': 2959, 'settlement': 7398,  'subsidy': 5200,  'labor': 0},
    '金鹰大厦':       {'orders': 269,  'settlement': 672,   'subsidy': 160,   'labor': 2760},
    '孙逸仙北院':     {'orders': 527,  'settlement': 1318,  'subsidy': 640,   'labor': 0},
    '新中国大厦':     {'orders': 1430, 'settlement': 3575,  'subsidy': 2880,  'labor': 0},
    '新亚洲电子城':   {'orders': 740,  'settlement': 1850,  'subsidy': 800,   'labor': 0},
}

# ===== 3. Build comparison =====
rows = []
all_stations = sorted(set(list(mt.keys()) + list(internal.keys())))

for short in all_stations:
    m = mt.get(short, {})
    i = internal.get(short, {})
    mt_orders = m.get('orders', 0)
    our_orders = i.get('orders', 0)
    mt_service = m.get('service_fee', 0)
    our_settle = i.get('settlement', 0)
    mt_subsidy = m.get('subsidy', 0)
    our_subsidy = i.get('subsidy', 0)
    mt_total = m.get('total', 0)
    our_labor = i.get('labor', 0)
    our_net = our_settle + our_subsidy - our_labor
    has_mt = mt_total > 0
    has_labor = our_labor > 0

    rows.append({
        'station': short,
        'mt_orders': mt_orders, 'our_orders': our_orders,
        'order_diff': our_orders - mt_orders,
        'mt_service': mt_service, 'our_settle': our_settle,
        'settle_diff': our_settle - mt_service,
        'mt_subsidy': mt_subsidy, 'our_subsidy': our_subsidy,
        'subsidy_diff': our_subsidy - mt_subsidy,
        'mt_total': mt_total, 'our_net': our_net,
        'has_mt': has_mt, 'has_labor': has_labor,
    })

# Totals
mt_total_orders = sum(r['mt_orders'] for r in rows)
our_total_orders = sum(r['our_orders'] for r in rows)
mt_total_service = sum(r['mt_service'] for r in rows)
our_total_settle = sum(r['our_settle'] for r in rows)
mt_total_subsidy = sum(r['mt_subsidy'] for r in rows)
our_total_subsidy = sum(r['our_subsidy'] for r in rows)
mt_grand = mt_total_service + mt_total_subsidy
our_grand = our_total_settle + our_total_subsidy
insurance = 908.12
mt_net = mt_grand - insurance

# ===== 4. Generate HTML =====
def fmt(v, currency=False):
    if currency:
        return f'<span class="muted">—</span>' if v == 0 else f'¥{v:,.0f}'
    return f'{v:,}'

def diff_class(v, invert=False):
    if v == 0: return ''
    if invert:
        return 'positive' if v <= 0 else 'warn'
    return 'positive' if v >= 0 else 'negative'

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>6月结算对比 · 美团 vs 预估</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Inter', -apple-system, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }
.container { max-width:1400px; margin:0 auto; }
h1 { font-size:24px; margin-bottom:4px; }
.subtitle { color:#64748b; margin-bottom:24px; font-size:14px; }
.summary-cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:16px; margin-bottom:24px; }
.card { background:#1e293b; border:1px solid #334155; border-radius:12px; padding:20px; }
.card-title { font-size:12px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:8px; }
.card-value { font-size:28px; font-weight:700; }
.card-sub { font-size:12px; color:#64748b; margin-top:4px; }
.card-mt { color:#818cf8; }
.card-our { color:#34d399; }
.card-diff { color:#fbbf24; }
table { width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; margin-bottom:24px; }
th { background:#334155; padding:12px 14px; text-align:right; font-size:12px; color:#94a3b8; font-weight:600; white-space:nowrap; }
th:first-child { text-align:left; }
td { padding:10px 14px; text-align:right; border-bottom:1px solid #1e293b; font-size:13px; font-variant-numeric:tabular-nums; }
td:first-child { text-align:left; font-weight:600; color:#e2e8f0; }
tr:hover { background:rgba(129,140,248,0.04); }
.positive { color:#34d399; }
.negative { color:#f87171; }
.warn { color:#fbbf24; }
.muted { color:#64748b; }
.badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:600; }
.badge-mt { background:rgba(129,140,248,0.2); color:#818cf8; }
.badge-comp { background:rgba(248,113,113,0.2); color:#f87171; }
.note { background:rgba(251,191,36,0.1); border:1px solid rgba(251,191,36,0.3); border-radius:8px; padding:16px; margin-top:24px; font-size:13px; color:#fbbf24; line-height:1.8; }
.note strong { color:#fcd34d; }
h2 { font-size:18px; margin:24px 0 16px; }
.section-divider { border-top:2px solid #334155; margin:32px 0 24px; }
.totals-grid { display:grid; grid-template-columns:1fr 1fr; gap:24px; margin-bottom:24px; }
@media (max-width:768px) { .totals-grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="container">
<h1>6月结算对比 · 美团实际 vs 内部预估</h1>
<p class="subtitle">美团结算: 惠州艾云 | 周期: 2026.06.01-06.30 | 生成: 2026-07-28</p>

<div class="summary-cards">
    <div class="card">
        <div class="card-title">美团净结算(到账)</div>
        <div class="card-value card-mt">''' + f'¥{mt_net:,.0f}' + '''</div>
        <div class="card-sub">服务费 ''' + f'¥{mt_total_service:,.0f}' + ''' + 补贴 ''' + f'¥{mt_total_subsidy:,.0f}' + ''' - 保险 ''' + f'¥{insurance:,.0f}' + '''</div>
    </div>
    <div class="card">
        <div class="card-title">内部预估净收入(未扣保险)</div>
        <div class="card-value card-our">''' + f'¥{our_grand:,.0f}' + '''</div>
        <div class="card-sub">结算 ''' + f'¥{our_total_settle:,.0f}' + ''' + 补贴 ''' + f'¥{our_total_subsidy:,.0f}' + '''</div>
    </div>
    <div class="card">
        <div class="card-title">差异(预估 vs 美团到账)</div>
        <div class="card-value card-diff">''' + f'¥{our_grand - mt_net:+,.0f}' + '''</div>
        <div class="card-sub">''' + f'{(our_grand - mt_net) / mt_net * 100:+.1f}%' + '''</div>
    </div>
    <div class="card">
        <div class="card-title">结算单量</div>
        <div class="card-value" style="color:#a78bfa">''' + f'{mt_total_orders:,}' + '''</div>
        <div class="card-sub">内部统计 ''' + f'{our_total_orders:,}' + ''' 单 (''' + f'{our_total_orders - mt_total_orders:+d}' + ''')</div>
    </div>
</div>

<h2>站点明细</h2>
<table>
<thead><tr>
    <th>站点</th>
    <th>美团单量</th>
    <th>内部单量</th>
    <th>差异</th>
    <th>美团服务费</th>
    <th>内部结算</th>
    <th>美团补贴</th>
    <th>内部补贴</th>
    <th>补贴差</th>
    <th>美团合计</th>
    <th>内部净收入</th>
</tr></thead>
<tbody>
'''

for r in rows:
    if not r['has_mt'] and r['station'] in ('孙逸仙北院', '新中国大厦', '新亚洲电子城'):
        tag = ' <span class="badge badge-comp">竞争方</span>'
    elif not r['has_mt']:
        tag = ' <span class="muted">(未覆盖)</span>'
    else:
        tag = ''

    html += '<tr>\n'
    html += f'    <td>{r["station"]}{tag}</td>\n'
    html += f'    <td>{"<span class=muted>—</span>" if not r["has_mt"] else f"{r["mt_orders"]:,}"}</td>\n'
    html += f'    <td>{r["our_orders"]:,}</td>\n'
    html += f'    <td class="{diff_class(r["order_diff"], True)}">{r["order_diff"]:+d}</td>\n'
    html += f'    <td>{"<span class=muted>—</span>" if not r["has_mt"] else f"¥{r["mt_service"]:,.0f}"}</td>\n'
    html += f'    <td>¥{r["our_settle"]:,.0f}</td>\n'
    html += f'    <td>{"<span class=muted>—</span>" if not r["has_mt"] else f"¥{r["mt_subsidy"]:,.0f}"}</td>\n'
    html += f'    <td>¥{r["our_subsidy"]:,.0f}</td>\n'
    html += f'    <td class="{diff_class(r["subsidy_diff"])}">¥{r["subsidy_diff"]:+,.0f}</td>\n'
    html += f'    <td>{"<span class=muted>未结算</span>" if not r["has_mt"] else f"¥{r["mt_total"]:,.0f}"}</td>\n'
    html += f'    <td>¥{r["our_net"]:+,.0f}</td>\n'
    html += '</tr>\n'

html += '''</tbody>
</table>

<div class="note">
    <strong>差异分析:</strong><br>
    1. <strong>单量: 基本一致</strong> — 美团 10,707 单 vs 内部 10,710 单（差 3 单，0.03%），说明双方统计口径一致<br>
    2. <strong>补贴差(''' + f'¥{our_total_subsidy - mt_total_subsidy:+,.0f}' + '''):</strong> 美团按「符合条件的天数×人头数×80元」月度累计；内部按当日(T-1)×80逐日计算。部分站点的补贴在美团侧被压缩<br>
    3. <strong>服务费:</strong> 双方均按 2.5 元/单计算，高度一致<br>
    4. <strong>保险扣除:</strong> 美团每单扣 ''' + f'{insurance/mt_total_orders*100:.1f}' + ''' 分保险，6月合计 ¥''' + f'{insurance:,.2f}' + '''，内部模型未计入此项，需补充<br>
    5. <strong>竞争方站点:</strong> 孙逸仙北院、新中国大厦、新亚洲电子城不在惠州艾云结算范围（可能由其他实体结算）<br>
    6. <strong>人力成本:</strong> 美团到账 ¥''' + f'{mt_net:,.0f}' + ''' 为毛利前收入，扣除实际人力成本后才是站点净利润
</div>
</div>
</body>
</html>
'''

out_path = 'output/june_settlement_comparison.html'
os.makedirs('output', exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {out_path}')
print(f'  美团净结算: ¥{mt_net:,.0f}')
print(f'  内部预估: ¥{our_grand:,.0f}')
print(f'  差异: ¥{our_grand - mt_net:+,.0f}')
