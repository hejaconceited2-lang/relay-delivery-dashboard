"""
审计脚本: 运营看板 vs 原始数据 全量核对
"""
import sys, os, re, glob
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from datetime import datetime

BASE = r'D:\CC\接力送日订单'
SETTLEMENT = 2.5
LABOR_RATE = 30
HOURS = 3
MATERIAL = 100/30
SUBSIDY_UNIT = 80
THRESHOLD = 20

COMPETITORS = {
    '分段履约广州新中国大厦', '分段履约广州新亚洲电子城',
    '分段履约广州孙逸仙北院'
}
STATION_HOURS = {'分段履约广州绿地星玥': 10}
STATION_LABOR_RATE = {'分段履约广州绿地星玥': 23}

HOURS_OVERRIDES = {
    '2026-06-18': {
        '分段履约广州华林国际C馆': 1.5,
    },
}

# 已知边界情况（不视为错误）
KNOWN_EDGE_CASES = {
    ('06/15', '珠江国际轻纺城'): '全单取消, 编制=0, KNOWN_STAFF回退到3',
}

errors = []
warnings = []

# ============================
# Part 1: 逐日逐站核对
# ============================
print('=' * 80)
print('[审计1] 逐日 利润线·编制·人均 vs 源数据')
print('=' * 80)

dates = sorted(
    d for d in os.listdir(BASE)
    if len(d) == 8 and d[2] == '-' and d[5] == '-'
    and os.path.isdir(os.path.join(BASE, d))
)

for dd in dates:
    candidates = glob.glob(os.path.join(BASE, dd, '*.xls')) + \
                 glob.glob(os.path.join(BASE, dd, '*.xlsx'))
    if not candidates:
        continue
    df = pd.read_excel(candidates[0])
    df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

    total = len(df)
    done = (df['物流单状态'] == '已送达').sum()
    canc = (df['物流单状态'] == '已取消').sum()
    pickup = (df['物流单状态'] == '已取货').sum()
    if total != done + canc + pickup:
        d_short = f'{dd[3:5]}/{dd[6:8]}'
        errors.append(f'[{d_short}] 状态合计: total={total} != {done}+{canc}+{pickup}={done+canc+pickup}')

    rider_cols = [c for c in df.columns
                  if c.startswith('经手骑手') and c != '经手骑手1']

    date_obj = datetime.strptime(f'20{dd[0:2]}-{dd[3:5]}-{dd[6:8]}', '%Y-%m-%d')
    mdd = date_obj.strftime('%m%d')
    html_path = os.path.join(BASE, f'{mdd}.html')

    if not os.path.exists(html_path):
        errors.append(f'[{dd}] HTML缺失: {mdd}.html')
        continue

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    for s in sorted(df['站点名称'].unique()):
        sdf = df[df['站点名称'] == s]
        cnt = len(sdf)
        grp = '竞争方' if s in COMPETITORS else '我方'
        if grp == '竞争方':
            continue

        # 编制检测
        riders = set()
        for col in rider_cols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        detected = len(riders) or 0

        per = cnt / detected if detected > 0 else None
        canc_comp = sdf.loc[sdf['物流单状态'] == '已取消', '订单实付'].sum()

        # UE 计算
        settlement = cnt * SETTLEMENT
        date_full = f'20{dd[0:2]}-{dd[3:5]}-{dd[6:8]}'
        hours_per = HOURS_OVERRIDES.get(date_full, {}).get(s,
                    STATION_HOURS.get(s, HOURS))
        rate = STATION_LABOR_RATE.get(s, LABOR_RATE)
        labor = detected * hours_per * rate
        material = MATERIAL
        meets = per and per >= THRESHOLD if per else False
        subsidy = (detected - 1) * SUBSIDY_UNIT if meets else 0
        profit = settlement + subsidy - labor - material - canc_comp

        short = s.replace('分段履约广州', '')
        sid = short.replace(' ', '_')
        d_short = f'{dd[3:5]}/{dd[6:8]}'

        # 检查 HTML 中声明的 orders / staff
        panel_match = re.search(
            rf'id="tab_{re.escape(sid)}".*?data-orders="(\d+)".*?data-staff="(\d+)"',
            html, re.DOTALL
        )
        if panel_match:
            html_orders = int(panel_match.group(1))
            html_staff = int(panel_match.group(2))
            if html_orders != cnt:
                errors.append(f'[{d_short}] {short}: HTML单量{html_orders} != 实际{cnt}')
            if html_staff != detected:
                if (d_short, short) in KNOWN_EDGE_CASES:
                    warnings.append(f'[{d_short}] {short}: 编制{html_staff}(KNOWN_STAFF回退) != 实际{detected} [{KNOWN_EDGE_CASES[(d_short, short)]}]')
                else:
                    errors.append(f'[{d_short}] {short}: HTML编制{html_staff} != 实际{detected}')
        else:
            warnings.append(f'[{d_short}] {short}: tab_panel 未匹配 (sid={sid})')

        # 检查利润线净利
        pl_match = re.search(
            rf'id="profit_line_{re.escape(sid)}">.*?净利 ¥([+-]?[\d,]+)',
            html, re.DOTALL
        )
        if pl_match:
            html_profit = int(pl_match.group(1).replace(',', '').replace('+', ''))
            expected = int(round(profit))
            if abs(html_profit - expected) > 2:
                if (d_short, short) in KNOWN_EDGE_CASES:
                    warnings.append(f'[{d_short}] {short}: 净利差(编制回退导致) [{KNOWN_EDGE_CASES[(d_short, short)]}]')
                else:
                    errors.append(
                        f'[{d_short}] {short}: HTML净利{html_profit} != 预期{expected} '
                        f'(结算{settlement:.0f}+补贴{subsidy:.0f}-人力{labor:.0f}'
                        f'-物料{material:.1f}-赔偿{canc_comp:.0f})'
                    )

print(f'  检查 {len(dates)} 天, {sum(1 for d in dates if glob.glob(os.path.join(BASE,d,"*.xls")) or glob.glob(os.path.join(BASE,d,"*.xlsx")))} 天有数据')
if errors:
    for e in errors[:20]:
        print(f'  ✗ {e}')
    if len(errors) > 20:
        print(f'  ... 共 {len(errors)} 个错误')
else:
    print('  ✓ 全部通过')
if warnings:
    for w in warnings[:5]:
        print(f'  ~ {w}')

# ============================
# Part 2: 全量汇总
# ============================
print()
print('=' * 80)
print('[审计2] index.html 累计 vs 实际')
print('=' * 80)

actual_cum = 0
actual_done = 0
actual_canc = 0
for dd in dates:
    candidates = glob.glob(os.path.join(BASE, dd, '*.xls')) + \
                 glob.glob(os.path.join(BASE, dd, '*.xlsx'))
    if not candidates:
        continue
    df = pd.read_excel(candidates[0])
    df = df[df['站点名称'].str.contains('分段履约', na=False)]
    actual_cum += len(df)
    actual_done += (df['物流单状态'] == '已送达').sum()
    actual_canc += (df['物流单状态'] == '已取消').sum()

with open(os.path.join(BASE, 'index.html'), 'r', encoding='utf-8') as f:
    idx = f.read()

cum_match = re.search(r'累计订单.*?</div>\s*<div[^>]*>([\d,]+)', idx, re.DOTALL)
if cum_match:
    declared = int(cum_match.group(1).replace(',', ''))
    if declared == actual_cum:
        print(f'  ✓ 累计单量一致: {actual_cum:,}')
    else:
        print(f'  ✗ 声明{declared:,} != 实际{actual_cum:,}')

print(f'  实际完成: {actual_done:,} ({actual_done/actual_cum*100:.1f}%)')
print(f'  实际取消: {actual_canc:,} ({actual_canc/actual_cum*100:.1f}%)')

# ============================
# Part 3: 6/23 详表
# ============================
print()
print('=' * 80)
print('[审计3] 6/23 逐站UE校对')
print('=' * 80)

dd = '26-06-23'
candidates = glob.glob(os.path.join(BASE, dd, '*.xls')) + \
             glob.glob(os.path.join(BASE, dd, '*.xlsx'))
df = pd.read_excel(candidates[0])
df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

with open(os.path.join(BASE, '0623.html'), 'r', encoding='utf-8') as f:
    html = f.read()

rider_cols = [c for c in df.columns
              if c.startswith('经手骑手') and c != '经手骑手1']

print(f'{"站点":<14s} {"单量":>4s} {"编制":>4s} {"人均":>6s} {"达标":>4s} '
      f'{"结算":>7s} {"人力":>7s} {"补贴":>6s} {"赔偿":>7s} {"净利":>8s} | HTML利润')
print('-' * 95)

total_profit = 0
html_total_profit = 0

for s in sorted(df['站点名称'].unique()):
    sdf = df[df['站点名称'] == s]
    cnt = len(sdf)
    grp = '竞争方' if s in COMPETITORS else '我方'
    short = s.replace('分段履约广州', '')
    sid = short.replace(' ', '_')

    riders = set()
    for col in rider_cols:
        if col in df.columns:
            for r in sdf[col].dropna():
                riders.add(str(r).strip())
    detected = len(riders) or 0

    per = cnt / detected if detected > 0 else 0
    canc_comp = sdf.loc[sdf['物流单状态'] == '已取消', '订单实付'].sum()

    if grp == '竞争方':
        print(f'{short:<14s} {cnt:4d} | 竞争方')
        continue

    settlement = cnt * SETTLEMENT
    hours_per = STATION_HOURS.get(s, HOURS)
    rate = STATION_LABOR_RATE.get(s, LABOR_RATE)
    labor = detected * hours_per * rate
    material = MATERIAL
    meets = per >= THRESHOLD
    subsidy = (detected - 1) * SUBSIDY_UNIT if meets else 0
    profit = settlement + subsidy - labor - material - canc_comp
    total_profit += profit

    # HTML profit
    pl_match = re.search(
        rf'id="profit_line_{re.escape(sid)}">.*?净利 ¥([+-]?[\d,]+)',
        html, re.DOTALL
    )
    h_profit = int(pl_match.group(1).replace(',', '').replace('+', '')) if pl_match else None
    if h_profit is not None:
        html_total_profit += h_profit

    mark = '✓' if (h_profit and abs(h_profit - round(profit)) <= 2) else '✗'
    print(f'{mark}{short:<13s} {cnt:4d} {detected:4d} {per:6.1f} '
          f'{"是" if meets else "否":>4s} '
          f'¥{settlement:6.0f} ¥{labor:5.0f} {subsidy:6.0f} '
          f'-¥{canc_comp:5.0f} ¥{profit:+8.0f} | '
          f'{"¥"+str(h_profit) if h_profit is not None else "N/A"}')

print('-' * 95)
print(f'{"合计":<14s} {"":>4s} {"":>4s} {"":>6s} {"":>4s} {"":>7s} {"":>7s} {"":>6s} {"":>7s} ¥{total_profit:+8.0f} | ¥{html_total_profit:+8.0f}')

# ============================
# Part 4: UE 分析页核对
# ============================
print()
print('=' * 80)
print('[审计4] 0623_ue.html vs 逐站汇总')
print('=' * 80)

with open(os.path.join(BASE, '0623_ue.html'), 'r', encoding='utf-8') as f:
    ue = f.read()

# 提取总收入
rev_match = re.search(r'总收入.*?¥([\d,]+)', ue, re.DOTALL)
if rev_match:
    ue_rev = int(rev_match.group(1).replace(',', ''))
    actual_rev = sum(
        cnt * SETTLEMENT
        for s in df['站点名称'].unique()
        if s not in COMPETITORS
        for cnt in [len(df[df['站点名称'] == s])]
    )
    if ue_rev == int(actual_rev):
        print(f'  ✓ 总收入一致: ¥{ue_rev:,}')
    else:
        print(f'  ✗ UE总收入{ue_rev:,} != 实际{actual_rev:,.0f}')

# 提取日净利
np_match = re.search(r'日净利.*?¥([+-]?[\d,]+)', ue, re.DOTALL)
if np_match:
    ue_np = int(np_match.group(1).replace(',', '').replace('+', ''))
    actual_np = round(total_profit)
    if abs(ue_np - actual_np) <= 3:
        print(f'  ✓ 日净利一致: ¥{ue_np:+,}')
    else:
        print(f'  ✗ UE日净利{ue_np:+,} != 实际约{actual_np:+,}')

# ============================
# Part 5: 承包商/中介看板
# ============================
print()
print('=' * 80)
print('[审计5] 承包商 & 中介 看板')
print('=' * 80)

for fname in ['lvdi_contractor.html', 'lvdi_intermediary.html']:
    path = os.path.join(BASE, fname)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Quick check for data presence
        if '绿地星玥' in content and '珠江国际' in content:
            print(f'  ✓ {fname} 两站点数据均存在')
        else:
            print(f'  ⚠ {fname} 缺站点数据')

# ============================
# Summary
# ============================
print()
print('=' * 80)
print('审计结论')
print('=' * 80)
if errors:
    print(f'  ✗ {len(errors)} 个错误需修复')
else:
    print(f'  ✓ 利润线/编制/人均: 全部一致')
print(f'  ⚡ 警告: {len(warnings)} 条 (多为ID匹配小问题)')
