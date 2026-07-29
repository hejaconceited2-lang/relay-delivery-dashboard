"""
6月总结算 — 简化版
"""
import pandas as pd, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')
from parse_payroll import parse_payroll

fp = '6月美团结算/202606-艾云-20260727.xlsx'
df_s = pd.read_excel(fp, sheet_name=2, engine='calamine')
mt = {}
for _, row in df_s.iterrows():
    sname = str(row['station_name']).replace('分段履约广州', '')
    if sname == 'nan' or '总计' in sname: continue
    short = '中大附三岭南医院' if sname == '中大附属岭南医院' else sname
    mt[short] = {'orders': int(row['6月总结算单量']), 'service_fee': float(row['按单服务费']),
                 'subsidy': float(row['人头补贴费']), 'total': float(row['合计'])}

payroll_path = '接力送真实人力计薪/接力送计薪表格.xlsx'
daily_labor, _, _ = parse_payroll(payroll_path)
station_labor = {}
for date_str, costs in daily_labor.items():
    if date_str.startswith('2026-06'):
        for sf, c in costs.items():
            station_labor[sf.replace('分段履约广州', '')] = station_labor.get(sf.replace('分段履约广州', ''), 0) + c

INS = 908.12; INS_PER = INS / sum(v['orders'] for v in mt.values())
CONTRACT = {'绿地星玥', '珠江国际轻纺城'}

owners = [
    ('陈贤乡', ['中大附属第六医院']),
    ('赵金荣', ['绿地星玥', '珠江国际轻纺城', '万科欧泊']),
    ('欧金标', ['中大附三岭南医院', '云升科技园']),
]
company_stations = ['和业广场', '万菱广场', '金鹰大厦', '汇德国际', '华林国际C馆']

all_labor = sum(station_labor.values())
MT_TOTAL = sum(v['total'] for v in mt.values())
VAT_RATE = 0.06

# 物料成本（公司垫付，承包站点对方自理）
BASE_MATERIAL = 200  # 每站基础
EXTRA_MATERIAL = {'万科欧泊': 1400 + 135 + 259 + 249}  # 额外物料

def get_material(short):
    if short in CONTRACT:
        return 0  # 承包站点对方自理
    return BASE_MATERIAL + EXTRA_MATERIAL.get(short, 0)

rows = []
total_co = total_ow = 0
for owner, stations in owners:
    co_sum = ow_sum = 0
    for short in stations:
        m = mt.get(short)
        if not m: continue
        o, s, sub = m['orders'], m['service_fee'], m['subsidy']
        ins = round(INS_PER * o, 2)
        mt_in = s + sub
        vat = mt_in * VAT_RATE  # VAT按美团到账比例分摊
        material = get_material(short)
        if short in CONTRACT:
            co = o * 0.5 - vat; ow = o * 2 + sub - ins
        else:
            labor = station_labor.get(short, 0)
            co = ow = (mt_in - ins - labor - material - vat) * 0.5
        co_sum += co; ow_sum += ow
        rows.append((short, o, mt_in, ins, station_labor.get(short,0), material, vat, co, ow, 'contract' if short in CONTRACT else 'regular', owner))
    total_co += co_sum; total_ow += ow_sum
    rows.append(('__SUB__', 0, 0, 0, 0, 0, 0, co_sum, ow_sum, 'sub', owner))

# Company
co_self = 0
for short in company_stations:
    m = mt.get(short)
    if m:
        labor = station_labor.get(short, 0); ins = round(INS_PER * m['orders'], 2)
        material = get_material(short)
        vat = m['total'] * VAT_RATE
        co_self += m['total'] - ins - labor - material - vat
        rows.append((short, m['orders'], m['total'], ins, labor, material, vat, m['total']-ins-labor-material-vat, 0, 'company', '公司自有'))

total_material = sum(get_material(s) for s in set(list(mt.keys())))
company_net = total_co + co_self
total_vat = MT_TOTAL * VAT_RATE

# Build HTML
body = ''
for owner, _ in owners:
    sub_rows = [r for r in rows if r[10] == owner]
    owner_net = sum(r[7] for r in sub_rows if r[0] != '__SUB__')
    owner_get = sum(r[8] for r in sub_rows if r[0] != '__SUB__')

    body += f'''<div class="group">
    <div class="group-title">{owner} <span style="color:#64748b;font-weight:400;font-size:13px">公司 {owner_net:+,.0f} · 负责人 {owner_get:+,.0f}</span></div>
    <table><thead><tr><th>点位</th><th>单量</th><th>美团到账</th><th>-保险</th><th>-人力</th><th>-物料</th><th>-增值税</th><th>公司</th><th>负责人</th></tr></thead><tbody>'''
    for r in sub_rows:
        if r[9] == 'sub': continue
        short, o, mt_in, ins, labor, material, vat, co, ow, model, _ = r
        tag = ' <b style="color:#fbbf24;font-size:10px">承包</b>' if model == 'contract' else ''
        if model == 'contract':
            labor_s = '<td class="muted">—</td><td class="muted">—</td>'
        else:
            labor_s = f'<td class="cost">-{labor:,.0f}</td>' if labor else '<td class="muted">—</td>'
            mat_s = f'<td class="cost">-{material:,.0f}</td>' if material else '<td class="muted">—</td>'
            labor_s = labor_s + mat_s
        body += f'<tr><td>{short}{tag}</td><td>{o:,}</td><td class="inc">+{mt_in:,.0f}</td><td class="cost">-{ins:,.0f}</td>{labor_s}<td class="cost">-{vat:,.0f}</td><td class="{"pos" if co>=0 else "neg"}">{co:+,.0f}</td><td class="{"pos" if ow>=0 else "neg"}">{ow:+,.0f}</td></tr>'
    body += '</tbody></table></div>'

# Self section
self_rows = [r for r in rows if r[10] == '公司自有']
body += f'''<div class="group self">
<div class="group-title">公司自有 <span style="color:#64748b;font-weight:400;font-size:13px">合计 {co_self:+,.0f}</span></div>
<table><thead><tr><th>点位</th><th>单量</th><th>美团到账</th><th>-保险</th><th>-人力</th><th>-物料</th><th>-增值税</th><th>结余</th></tr></thead><tbody>'''
for r in self_rows:
    short, o, mt_in, ins, labor, material, vat, co, _, _, _ = r
    body += f'<tr><td>{short}</td><td>{o:,}</td><td class="inc">+{mt_in:,.0f}</td><td class="cost">-{ins:,.0f}</td><td class="cost">-{labor:,.0f}</td><td class="cost">-{material:,.0f}</td><td class="cost">-{vat:,.0f}</td><td class="{"pos" if co>=0 else "neg"}">{co:+,.0f}</td></tr>'
body += '</tbody></table></div>'

html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>6月总结算</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Inter,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;font-size:14px}}
.container{{max-width:900px;margin:0 auto}}
h1{{font-size:20px;margin-bottom:4px}}
.sub{{color:#64748b;font-size:12px;margin-bottom:20px}}
.group{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 20px;margin-bottom:14px}}
.group.self{{opacity:.8;border-style:dashed}}
.group-title{{font-size:15px;font-weight:700;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:right;padding:8px 10px;color:#94a3b8;font-size:11px;font-weight:600;border-bottom:1px solid #334155}}
th:first-child{{text-align:left}}
td{{text-align:right;padding:7px 10px;border-bottom:1px solid #1e293b}}
td:first-child{{text-align:left;font-weight:500}}
tr:hover{{background:rgba(129,140,248,.03)}}
.inc{{color:#34d399}}.cost{{color:#f87171}}.pos{{color:#34d399;font-weight:700}}.neg{{color:#f87171;font-weight:700}}.muted{{color:#64748b}}

.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px;text-align:center}}
.card-v{{font-size:22px;font-weight:700;margin-bottom:4px}}
.card-t{{font-size:10px;color:#94a3b8;text-transform:uppercase}}
.green{{color:#34d399}}.red{{color:#f87171}}.blue{{color:#818cf8}}.amber{{color:#fbbf24}}

.total-bar{{background:linear-gradient(135deg,#1e3a5f,#1e293b);border:1px solid #3b82f6;border-radius:10px;padding:16px 20px;margin-top:16px;display:flex;justify-content:space-between;align-items:center}}
.total-label{{font-size:13px;color:#94a3b8}}
.total-value{{font-size:24px;font-weight:700}}
.note{{color:#64748b;font-size:11px;margin-top:12px;line-height:1.6}}
.pnl table{{width:100%}}.pnl td{{padding:10px 12px;border-bottom:1px solid #1e293b;font-size:13px}}
.pnl .l{{text-align:left}}.pnl .r{{text-align:right;font-weight:600}}
.pnl tr.sec td{{background:#1e293b;color:#94a3b8;font-size:11px;font-weight:600}}
.pnl tr.total td{{border-top:2px solid #3b82f6;font-size:15px;font-weight:700;padding:14px 12px}}
</style></head><body>
<div class="container">
<h1>6月总结算</h1>
<div class="sub">美团结算 · 惠州艾云 · 2026年6月 · 保险 {INS_PER*100:.1f}分/单</div>

<div class="cards">
<div class="card"><div class="card-t">美团到账</div><div class="card-v blue">¥{sum(v["total"] for v in mt.values()):,.0f}</div></div>
<div class="card"><div class="card-t">保险</div><div class="card-v red">-¥{INS:,.0f}</div></div>
<div class="card"><div class="card-t">公司人力</div><div class="card-v red">-¥{all_labor:,.0f}</div></div>
<div class="card"><div class="card-t">增值税 6%</div><div class="card-v red">-¥{total_vat:,.0f}</div></div>
<div class="card"><div class="card-t">公司净利</div><div class="card-v {"green" if company_net>=0 else "red"}">{company_net:+,.0f}</div></div>
</div>

{body}

<div class="total-bar">
<div class="total-label">公司汇总净利<br><span style="font-size:11px;color:#64748b">到账 ¥{MT_TOTAL:,.0f} - 保险 ¥{INS:,.0f} - 人力 ¥{all_labor:,.0f} - 物料 ¥{total_material:,.0f} - 付负责人 ¥{total_ow:,.0f} - 增值税 ¥{total_vat:,.0f} - 自有站 ¥{-co_self:,.0f}</span></div>
<div class="total-value {"green" if company_net>=0 else "red"}">{company_net:+,.0f}</div>
</div>

<div class="note">
常规站点结余(美团到账-保险-人力-增值税)由公司/负责人各50%分摊 · 承包站点公司留0.5元/单，增值税由公司承担 · 物料费用待计入
</div>

<h2 style="margin-top:28px;font-size:16px;padding-bottom:8px;border-bottom:1px solid #334155">公司层面盈利</h2>
<div class="pnl">
<table>
<tr><td class="l">美团总结算</td><td class="r inc">+¥{MT_TOTAL:,.0f}</td></tr>
<tr><td class="l">保险</td><td class="r cost">-¥{INS:,.0f}</td></tr>
<tr><td class="l">增值税 6%</td><td class="r cost">-¥{total_vat:,.0f}</td></tr>
<tr class="sec"><td class="l">人力成本（公司垫付）</td><td class="r cost">-¥{all_labor:,.0f}</td></tr>
<tr><td class="l">物料成本（公司垫付）</td><td class="r cost">-¥{total_material:,.0f}</td></tr>
<tr class="sec"><td class="l">应付负责人分红</td><td class="r cost">-¥{total_ow:,.0f}</td></tr>
<tr class="total"><td class="l">公司净利</td><td class="r {"pos" if company_net>=0 else "neg"}">{company_net:+,.0f}</td></tr>
</table>
</div>

<div style="margin-top:20px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
<div class="card"><div class="card-t">合伙人站点公司分成</div><div class="card-v {"green" if total_co>=0 else "red"}">{total_co:+,.0f}</div></div>
<div class="card"><div class="card-t">自有站点盈亏</div><div class="card-v {"green" if co_self>=0 else "red"}">{co_self:+,.0f}</div></div>
<div class="card"><div class="card-t">最终净利润</div><div class="card-v {"green" if company_net>=0 else "red"}">{company_net:+,.0f}</div></div>
</div>
</div></body></html>'''

out = 'output/june_summary.html'
os.makedirs('output', exist_ok=True)
with open(out, 'w', encoding='utf-8') as f: f.write(html)
with open('analysis/june_summary.html', 'w', encoding='utf-8') as f: f.write(html)
print(f'[OK] {out}')
print(f'公司净利: {company_net:+,.0f}')
