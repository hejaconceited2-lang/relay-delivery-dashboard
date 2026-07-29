"""
生成点位负责人结算 + 公司层面盈亏页面
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

total_insurance = 908.12
total_mt_orders = sum(v['orders'] for v in mt.values())
ins_per_order = total_insurance / total_mt_orders

CONTRACT_STATIONS = {'绿地星玥', '珠江国际轻纺城'}

# ===== Per-owner payout calculation =====
owner_stations = {
    '陈贤乡': ['中大附属第六医院'],
    '赵金荣': ['绿地星玥', '万科欧泊', '珠江国际轻纺城'],
    '欧金标': ['中大附三岭南医院', '云升科技园'],
}

payout_rows = []
total_payout = 0

for owner, stations in owner_stations.items():
    owner_detail = []
    company_pays = 0  # 公司应付
    owner_owes = 0    # 负责人应给回公司

    for short in stations:
        m = mt.get(short)
        if not m:
            continue
        orders = m['orders']
        service = m['service_fee']
        subsidy = m['subsidy']
        ins = round(total_insurance * orders / total_mt_orders, 2)

        if short in CONTRACT_STATIONS:
            # Contract: company pays 2元/单, subsidy passes to operator
            payout = orders * 2.0 + subsidy - ins
            note = f'{orders}单×¥2 + 补贴¥{subsidy:,.0f} - 保险¥{ins:,.0f}'
            model = 'contract'
            company_pays += payout
            owe = 0
        else:
            labor = station_labor.get(short, 0)
            balance = service + subsidy - ins - labor  # 结余
            owner_share = balance * 0.5  # 50%
            if owner_share >= 0:
                payout = owner_share
                owe = 0
                note = f'结余¥{balance:+,.0f} × 50%'
            else:
                payout = 0
                owe = -owner_share  # positive amount owed to company
                note = f'亏损¥{balance:+,.0f} × 50% → 负责人应补'
            company_pays += payout
            owner_owes += owe
            model = 'regular'

        owner_detail.append((short, orders, service, subsidy, ins,
                           station_labor.get(short, 0) if model == 'regular' else 0,
                           payout if payout > 0 else -owe, model, note))

    net = company_pays - owner_owes
    total_payout += company_pays
    payout_rows.append((owner, owner_detail, company_pays, owner_owes, net))

# ===== Company P&L =====
# Revenue: Meituan settlement for ALL 11 settlement stations
company_revenue_settlement = sum(v['total'] for v in mt.values())  # service fee + subsidy

# Deduct insurance (already taken from total)
company_revenue_after_ins = company_revenue_settlement - total_insurance

# Costs
total_labor_paid = sum(station_labor.values())  # company paid labor
total_payout_to_owners = sum(r[4] for r in payout_rows)  # net payout per owner

# Company net
contract_company_share = 0
for short in CONTRACT_STATIONS:
    m = mt.get(short)
    if m:
        contract_company_share += m['orders'] * 0.5

# For company P&L, the company's actual revenue is:
# - From regular stations: service fee + subsidy (all goes through company)
# - From contract stations: company keeps 0.5/单
# Company expenses:
# - Labor cost for regular stations
# - Payout to regular station owners
# - Contract payout (2元/单) to contract station operators
# - Insurance (already deducted)

# Regular stations company net
regular_revenue = 0
regular_labor = 0
regular_payout = 0
regular_insurance = 0
for owner, stations in owner_stations.items():
    for short in stations:
        m = mt.get(short)
        if not m or short in CONTRACT_STATIONS:
            continue
        regular_revenue += m['total']
        regular_labor += station_labor.get(short, 0)
        regular_insurance += round(total_insurance * m['orders'] / total_mt_orders, 2)

# Regular station payout is sum of owner share
for owner, detail, cp, ow, net in payout_rows:
    for d in detail:
        if d[7] == 'regular' and d[6] > 0:  # d[6]=payout, d[7]=model
            regular_payout += d[6]

regular_company_net = regular_revenue - regular_labor - regular_payout - regular_insurance

# Contract stations: company receives service+subsidy, passes subsidy+2元/单 to operator
contract_revenue = 0
contract_payout = 0
contract_insurance = 0
for short in CONTRACT_STATIONS:
    m = mt.get(short)
    if m:
        # Revenue includes subsidy (Meituan pays company, company passes to operator)
        contract_revenue += m['total']
        # Payout: 2元/单 + 补贴 passed through
        contract_payout += m['orders'] * 2.0 + m['subsidy']
        contract_insurance += round(total_insurance * m['orders'] / total_mt_orders, 2)

contract_company_net = contract_revenue - contract_payout - contract_insurance

# Company self-operated stations
COMPANY_STATIONS = ['和业广场', '万菱广场', '金鹰大厦', '汇德国际', '华林国际C馆']
company_stations_revenue = 0
company_stations_labor = 0
company_stations_insurance = 0
for short in COMPANY_STATIONS:
    m = mt.get(short)
    if m:
        company_stations_revenue += m['total']
        company_stations_labor += station_labor.get(short, 0)
        company_stations_insurance += round(total_insurance * m['orders'] / total_mt_orders, 2)
company_self_net = company_stations_revenue - company_stations_labor - company_stations_insurance

# Grand total company
company_total_net = regular_company_net + contract_company_net + company_self_net

# ===== Build HTML =====
def money(v, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<span{c}>¥{v:+,.0f}</span>'

# Payout table
payout_html = ''
for owner, detail, company_pays, owner_owes, net in payout_rows:
    rows = ''
    for short, orders, service, subsidy, ins, labor, amount, model, note in detail:
        model_tag = ' <span style="font-size:10px;color:#fbbf24">承包</span>' if model == 'contract' else ''
        labor_str = f'<td class="cost">-¥{labor:,.0f}</td>' if model == 'regular' and labor else '<td class="muted">—</td>'
        if amount >= 0:
            amt_html = f'<td class="income"><strong>+¥{amount:,.0f}</strong></td>'
        else:
            amt_html = f'<td class="cost"><strong>-¥{-amount:,.0f}</strong></td>'
        rows += f'''<tr>
            <td>{short}{model_tag}</td>
            <td>{orders:,}</td>
            <td class="muted" style="font-size:11px">{note}</td>
            {labor_str}
            {amt_html}
        </tr>'''

    if net >= 0:
        summary = f'<span class="total-badge positive">公司应付 ¥{net:,.0f}</span>'
    else:
        summary = f'<span class="total-badge negative">负责人应退回 ¥{-net:,.0f}</span>'

    detail_note = ''
    if owner_owes > 0:
        detail_note = f'（含亏损分摊 ¥{owner_owes:,.0f}）'

    payout_html += f'''<div class="person-section">
    <div class="person-header">{owner} {summary} <span style="font-size:11px;color:#64748b">{detail_note}</span></div>
    <table>
        <thead><tr><th>点位</th><th>单量</th><th>计算过程</th><th>人力(公司垫)</th><th>金额(+/−)</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
</div>'''

# ===== Write HTML =====
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>6月点位结算 & 公司盈亏</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: 'Inter', -apple-system, sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
.container {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:22px; margin-bottom:4px; }}
h2 {{ font-size:17px; margin:28px 0 16px; padding-bottom:8px; border-bottom:1px solid #334155; }}
.subtitle {{ color:#64748b; margin-bottom:8px; font-size:13px; }}

.person-section {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px 20px; margin-bottom:16px; }}
.person-header {{ font-size:16px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:12px; }}
.total-badge {{ font-size:13px; padding:4px 12px; border-radius:6px; font-weight:600; }}
.total-badge.positive {{ background:rgba(52,211,153,0.15); color:#34d399; }}
.total-badge.negative {{ background:rgba(248,113,113,0.15); color:#f87171; }}

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

.cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap:12px; margin-bottom:20px; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px; }}
.card-title {{ font-size:11px; color:#94a3b8; margin-bottom:6px; }}
.card-value {{ font-size:22px; font-weight:700; }}
.card-sub {{ font-size:11px; color:#64748b; margin-top:4px; }}
.card-breakdown {{ font-size:11px; color:#94a3b8; margin-top:6px; line-height:1.6; }}

.pnl-row {{ display:grid; grid-template-columns:200px 1fr; gap:0; margin-bottom:20px; background:#1e293b; border-radius:12px; overflow:hidden; border:1px solid #334155; }}
.pnl-label {{ padding:12px 16px; font-weight:600; font-size:13px; border-bottom:1px solid #334155; }}
.pnl-value {{ padding:12px 16px; text-align:right; font-size:13px; border-bottom:1px solid #334155; font-weight:600; }}
.pnl-sub {{ grid-column:1/-1; padding:8px 16px; font-size:11px; color:#94a3b8; border-bottom:1px solid #1e293b; }}
.pnl-section {{ grid-column:1/-1; padding:10px 16px; font-size:12px; color:#818cf8; font-weight:600; background:#1e3a5f; }}
.pnl-total {{ grid-column:1/-1; padding:14px 16px; font-size:15px; font-weight:700; background:#0f172a; display:flex; justify-content:space-between; }}

.note {{ margin-top:24px; padding:16px; background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.2); border-radius:8px; font-size:12px; color:#fbbf24; line-height:1.8; }}
</style>
</head>
<body>
<div class="container">
<h1>6月点位结算 & 公司盈亏</h1>
<p class="subtitle">基于美团结算 | 2026年6月 | 惠州艾云 | 保险 {ins_per_order*100:.1f}分/单</p>

<!-- ====== Part 1: Payout to Owners ====== -->
<h2>一、应付点位负责人</h2>

<div class="cards">
    <div class="card">
        <div class="card-title">公司应付责任人</div>
        <div class="card-value income">¥{total_payout:,.0f}</div>
        <div class="card-sub">陈贤乡+赵金荣+欧金标</div>
    </div>
    <div class="card">
        <div class="card-title">责任人应退回公司</div>
        <div class="card-value cost">¥{sum(r[3] for r in payout_rows):,.0f}</div>
        <div class="card-sub">亏损站点50%分摊</div>
    </div>
    <div class="card">
        <div class="card-title">公司净支出</div>
        <div class="card-value" style="color:#fbbf24">¥{sum(r[4] for r in payout_rows):,.0f}</div>
        <div class="card-sub">应付 - 退回</div>
    </div>
</div>

{payout_html}

<!-- ====== Part 2: Company P&L ====== -->
<h2>二、公司层面盈亏</h2>

<div class="pnl-row">
    <div class="pnl-section">收入</div>
    <div class="pnl-section" style="text-align:right"></div>

    <div class="pnl-label">美团总结算(11站)</div>
    <div class="pnl-value income">+¥{company_revenue_settlement:,.0f}</div>
    <div class="pnl-sub">服务费 ¥{sum(v['service_fee'] for v in mt.values()):,.0f} + 补贴 ¥{sum(v['subsidy'] for v in mt.values()):,.0f}</div>

    <div class="pnl-label">保险扣除</div>
    <div class="pnl-value cost">-¥{total_insurance:,.0f}</div>
    <div class="pnl-sub">{total_mt_orders:,}单 × {ins_per_order*100:.1f}分/单</div>

    <div class="pnl-section">支出</div>
    <div class="pnl-section" style="text-align:right"></div>

    <div class="pnl-label">公司垫付人力(常规站)</div>
    <div class="pnl-value cost">-¥{regular_labor:,.0f}</div>
    <div class="pnl-sub">{len(station_labor)}站有计薪数据</div>

    <div class="pnl-label">应付责任人-常规站点</div>
    <div class="pnl-value cost">-¥{regular_payout:,.0f}</div>
    <div class="pnl-sub">仅结余为正的站点</div>

    <div class="pnl-label">应付责任人-承包站点</div>
    <div class="pnl-value cost">-¥{contract_payout:,.0f}</div>
    <div class="pnl-sub">含 2元/单 + 补贴 ¥{2960*2+5520:,.0f}(绿地) + ¥{383*2+320:,.0f}(珠江)</div>

    <div class="pnl-label">公司自有站人力</div>
    <div class="pnl-value cost">-¥{company_stations_labor:,.0f}</div>
    <div class="pnl-sub">和业+万菱+金鹰+汇德+华林</div>

    <div class="pnl-total">
        <span>公司6月净利润</span>
        <span class="{'positive' if company_total_net>=0 else 'negative'}">¥{company_total_net:+,.0f}</span>
    </div>
</div>

<div class="cards">
    <div class="card">
        <div class="card-title">常规站点公司净利</div>
        <div class="card-value {'positive' if regular_company_net>=0 else 'negative'}">¥{regular_company_net:+,.0f}</div>
        <div class="card-sub">收入 ¥{regular_revenue:,.0f} | 人力-¥{regular_labor:,.0f} | 分成-¥{regular_payout:,.0f}</div>
    </div>
    <div class="card">
        <div class="card-title">承包站点公司净利</div>
        <div class="card-value {'positive' if contract_company_net>=0 else 'negative'}">¥{contract_company_net:+,.0f}</div>
        <div class="card-sub">收入 ¥{contract_revenue:,.0f} | 付承包费-¥{contract_payout:,.0f} | 保险-¥{contract_insurance:,.0f}</div>
    </div>
    <div class="card">
        <div class="card-title">公司自有站净利</div>
        <div class="card-value {'positive' if company_self_net>=0 else 'negative'}">¥{company_self_net:+,.0f}</div>
        <div class="card-sub">收入 ¥{company_stations_revenue:,.0f} | 人力-¥{company_stations_labor:,.0f}</div>
    </div>
</div>

<div class="note">
    <strong>说明:</strong><br>
    1. 常规站点规则：结余(服务费+补贴-保险-人力)为正时才向负责人支付，亏损由公司承担<br>
    2. 承包站点规则：公司按 2元/单 支付给对方，补贴和保险由对方自理，公司净赚 0.5元/单<br>
    3. 万科欧泊亏损 ¥3,379，负责人承担50%(¥1,690)，从其他站点分成中抵扣<br>
    4. 分红比例、物料费用等未计入，待另行约定
</div>
</div>
</body>
</html>
'''

out_path = 'output/june_payout_pnl.html'
os.makedirs('output', exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

with open('analysis/june_payout_pnl.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'[OK] {out_path}')
print()
print('=== 公司与负责人结算 ===')
for owner, detail, company_pays, owner_owes, net in payout_rows:
    if net >= 0:
        print(f'{owner}: 公司应付 ¥{net:,.0f}')
    else:
        print(f'{owner}: 负责人应退回 ¥{-net:,.0f}')
print(f'公司净支出: ¥{total_payout_to_owners:,.0f}')
print()
print(f'=== 公司层面盈亏 ===')
print(f'美团到账(扣保险): ¥{company_revenue_after_ins:,.0f}')
print(f'垫付人力: -¥{regular_labor+company_stations_labor:,.0f}')
print(f'净付负责人: -¥{total_payout_to_owners:,.0f}')
print(f'公司净利: ¥{company_total_net:+,.0f}')
