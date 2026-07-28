"""
生成6月点位分红结算页面
"""
import pandas as pd, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')
from parse_payroll import parse_payroll

# ===== Data =====
fp = '6月美团结算/202606-艾云-20260727.xlsx'
df_s = pd.read_excel(fp, sheet_name=2, engine='calamine')

mt = {}
for _, row in df_s.iterrows():
    sname = str(row['station_name']).replace('分段履约广州', '')
    if sname == 'nan' or '总计' in sname:
        continue
    short = '中大附三岭南医院' if sname == '中大附属岭南医院' else sname
    mt[short] = {
        'orders': int(row['6月总结算单量']),
        'service_fee': float(row['按单服务费']),
        'subsidy': float(row['人头补贴费']),
        'total': float(row['合计']),
    }

payroll_path = '接力送真实人力计薪/接力送计薪表格.xlsx'
daily_labor, _, _ = parse_payroll(payroll_path)

station_labor = {}
for date_str, station_costs in daily_labor.items():
    if date_str.startswith('2026-06'):
        for station_full, cost in station_costs.items():
            short = station_full.replace('分段履约广州', '')
            station_labor[short] = station_labor.get(short, 0) + cost

owner_map = {
    '陈贤乡': ['中大附属第六医院'],
    '赵金荣': ['绿地星玥', '万科欧泊', '珠江国际轻纺城'],
    '欧金标': ['中大附三岭南医院', '云升科技园'],
    '郑峰': ['中大附属第三医院'],
    '陈家瑞': ['上城敏捷'],
    '公司': ['和业广场', '万菱广场', '金鹰大厦', '汇德国际', '华林国际C馆', '交易广场'],
}

total_insurance = 908.12
total_mt_orders = sum(v['orders'] for v in mt.values())
ins_per_order = total_insurance / total_mt_orders

# Build person rows
def build_person_rows(owner, stations):
    rows = []
    for short in stations:
        m = mt.get(short)
        if not m:
            continue
        orders = m['orders']
        service = m['service_fee']
        subsidy = m['subsidy']
        ins = round(total_insurance * orders / total_mt_orders, 2)
        if short in ('绿地星玥', '珠江国际轻纺城'):
            # Contract model: company pays 2元/单, operator handles everything
            company_net = orders * 0.5  # (2.5-2.0)=0.5/单
            rows.append((short, orders, service, subsidy, ins, 0, company_net, 'contract'))
        else:
            labor = station_labor.get(short, 0)
            net = service + subsidy - ins - labor
            rows.append((short, orders, service, subsidy, ins, labor, net, 'regular'))
    return rows

# Build HTML
html_parts = []
for owner in ['陈贤乡', '赵金荣', '欧金标', '郑峰', '陈家瑞']:
    stations = owner_map[owner]
    rows = build_person_rows(owner, stations)
    if not rows:
        html_parts.append(f'''<div class="person-section">
    <div class="person-header">{owner}</div>
    <div class="empty-note">6月无美团结算数据（站点尚未开始或未纳入结算）</div>
</div>''')
        continue

    total_net = sum(r[6] for r in rows)
    net_class = 'positive' if total_net >= 0 else 'negative'

    rows_html = ''
    for short, orders, service, subsidy, ins, labor, net, model in rows:
        nc = 'positive' if net >= 0 else 'negative'
        if model == 'contract':
            labor_str = '<td class="muted">承包制</td>'
        elif labor:
            labor_str = f'<td class="cost">-¥{labor:,.0f}</td>'
        else:
            labor_str = '<td class="muted">—</td>'
        rows_html += f'''<tr>
            <td>{short}{" <span style=font-size:10px;color:#fbbf24>承包</span>" if model=="contract" else ""}</td>
            <td>{orders:,}</td>
            <td class="income">¥{service:,.0f}</td>
            <td class="income">¥{subsidy:,.0f}</td>
            <td class="cost">-¥{ins:,.0f}</td>
            {labor_str}
            <td class="{nc}"><strong>¥{net:+,.0f}</strong></td>
        </tr>'''

    html_parts.append(f'''<div class="person-section">
    <div class="person-header">{owner} <span class="total-badge {net_class}">合计 ¥{total_net:+,.0f}</span></div>
    <table>
        <thead><tr>
            <th>点位</th><th>单量</th><th>服务费</th><th>补贴</th><th>保险</th><th>人力</th><th>结余</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>''')

# Company section
company_rows = build_person_rows('公司', owner_map['公司'])
company_net = sum(r[6] for r in company_rows)
company_html = ''
for short, orders, service, subsidy, ins, labor, net, model in company_rows:
    nc = 'positive' if net >= 0 else 'negative'
    if model == 'contract':
        labor_str = '<td class="muted">承包制</td>'
    elif labor:
        labor_str = f'<td class="cost">-¥{labor:,.0f}</td>'
    else:
        labor_str = '<td class="muted">—</td>'
    company_html += f'''<tr>
        <td>{short}</td>
        <td>{orders:,}</td>
        <td class="income">¥{service:,.0f}</td>
        <td class="income">¥{subsidy:,.0f}</td>
        <td class="cost">-¥{ins:,.0f}</td>
        {labor_str}
        <td class="{nc}"><strong>¥{net:+,.0f}</strong></td>
    </tr>'''

# Totals
all_person_net = sum(
    sum(r[6] for r in build_person_rows(o, owner_map[o]))
    for o in ['陈贤乡', '赵金荣', '欧金标']
)

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>6月点位分红结算</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Inter', -apple-system, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
.container {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
.subtitle {{ color:#64748b; margin-bottom:24px; font-size:13px; }}

.person-section {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px 20px; margin-bottom:20px; }}
.person-header {{ font-size:16px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:12px; }}
.total-badge {{ font-size:13px; padding:4px 12px; border-radius:6px; font-weight:600; }}
.total-badge.positive {{ background:rgba(52,211,153,0.15); color:#34d399; }}
.total-badge.negative {{ background:rgba(248,113,113,0.15); color:#f87171; }}

.empty-note {{ color:#64748b; font-size:13px; padding:8px 0; }}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#0f172a; padding:10px 12px; text-align:right; color:#94a3b8; font-weight:600; font-size:11px; }}
th:first-child {{ text-align:left; }}
td {{ padding:9px 12px; text-align:right; border-bottom:1px solid #1e293b; }}
td:first-child {{ text-align:left; font-weight:500; }}
tr:hover {{ background:rgba(129,140,248,0.03); }}

.income {{ color:#34d399; }}
.cost {{ color:#f87171; }}
.positive {{ color:#34d399; }}
.negative {{ color:#f87171; }}
.muted {{ color:#64748b; }}

.summary-cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px,1fr)); gap:12px; margin-bottom:24px; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px; }}
.card-title {{ font-size:11px; color:#94a3b8; margin-bottom:6px; }}
.card-value {{ font-size:22px; font-weight:700; }}
.card-sub {{ font-size:11px; color:#64748b; margin-top:4px; }}

.company-section {{ background:#1e293b; border:1px dashed #475569; border-radius:12px; padding:16px 20px; margin-top:24px; }}
.company-header {{ font-size:14px; color:#94a3b8; margin-bottom:12px; }}

.formula {{ background:rgba(129,140,248,0.08); border-radius:8px; padding:12px 16px; margin-bottom:20px; font-size:12px; color:#94a3b8; line-height:1.8; }}
.formula strong {{ color:#e2e8f0; }}
</style>
</head>
<body>
<div class="container">
<h1>6月点位分红结算</h1>
<p class="subtitle">基于美团结算数据 | 2026年6月 | 惠州艾云</p>

<div class="formula">
    <strong>常规点位:</strong> 结余 = 服务费(2.5元/单) + 补贴 - 保险({ins_per_order*100:.1f}分/单) - 公司垫付人力<br>
    <strong>承包点位(绿地星玥/珠江国际轻纺城):</strong> 公司按 2元/单 结算给对方，公司留 0.5元/单；补贴、保险、人力等由对方全权负责
</div>

<div class="summary-cards">
    <div class="card">
        <div class="card-title">美团到账</div>
        <div class="card-value" style="color:#818cf8">¥{sum(v['total'] for v in mt.values()):,.0f}</div>
        <div class="card-sub">服务费 ¥{sum(v['service_fee'] for v in mt.values()):,.0f} + 补贴 ¥{sum(v['subsidy'] for v in mt.values()):,.0f}</div>
    </div>
    <div class="card">
        <div class="card-title">保险扣除</div>
        <div class="card-value" style="color:#f87171">-¥{total_insurance:,.0f}</div>
        <div class="card-sub">{ins_per_order*100:.1f}分/单 × {total_mt_orders:,}单</div>
    </div>
    <div class="card">
        <div class="card-title">公司垫付人力</div>
        <div class="card-value" style="color:#f87171">-¥{sum(station_labor.values()):,.0f}</div>
        <div class="card-sub">{len(station_labor)}站有计薪数据</div>
    </div>
    <div class="card">
        <div class="card-title">个人点位结余合计</div>
        <div class="card-value" style="color:{'#34d399' if all_person_net>=0 else '#f87171'}">¥{all_person_net:+,.0f}</div>
        <div class="card-sub">陈贤乡+赵金荣+欧金标</div>
    </div>
</div>

{''.join(html_parts)}

<div class="company-section">
    <div class="company-header">公司自有 · 6月结余 <span class="total-badge {'positive' if company_net>=0 else 'negative'}" style="margin-left:8px;">合计 ¥{company_net:+,.0f}</span></div>
    <table>
        <thead><tr>
            <th>点位</th><th>单量</th><th>服务费</th><th>补贴</th><th>保险</th><th>人力</th><th>结余</th>
        </tr></thead>
        <tbody>{company_html}</tbody>
    </table>
</div>

<div style="margin-top:24px; padding:16px; background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.2); border-radius:8px; font-size:12px; color:#fbbf24; line-height:1.8;">
    <strong>说明:</strong><br>
    1. 绿地星玥、珠江国际轻纺城为承包模式：公司按2元/单结算，公司净留0.5元/单<br>
    2. 保险按各站点单量比例分摊（总额 ¥{total_insurance:,.2f}）<br>
    3. 郑峰(中大附属第三医院)、陈家瑞(敏捷上城国际) 6月未纳入美团结算<br>
    4. 分红比例、物料费用等需另行约定
</div>
</div>
</body>
</html>
'''

out_path = 'output/june_profit_sharing.html'
os.makedirs('output', exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Also copy to root
with open('june_profit_sharing.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {out_path}')
print(f'  个人点位结余: 陈贤乡 ¥{build_person_rows("陈贤乡",owner_map["陈贤乡"])[0][6]:,.0f} | 赵金荣 ¥{sum(r[6] for r in build_person_rows("赵金荣",owner_map["赵金荣"])):,.0f} | 欧金标 ¥{sum(r[6] for r in build_person_rows("欧金标",owner_map["欧金标"])):,.0f}')
print(f'  公司自有: ¥{company_net:,.0f}')
