"""美团 vs 我们 - 人头激励对比"""
import pandas as pd
import os, glob, sys

# Force utf-8 output
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = r'D:\CC\接力送日订单'
MT_FILE = os.path.join(BASE_DIR, '202606-艾云.xlsx')

SID_MAP = {
    2091043: ('和业广场', '分段履约广州和业广场'),
    2091045: ('华林国际C馆', '分段履约广州华林国际C馆'),
    2091340: ('汇德国际', '分段履约广州汇德国际'),
    2091081: ('金鹰大厦', '分段履约广州金鹰大厦'),
    2091021: ('绿地星玥', '分段履约广州绿地星玥'),
    2090524: ('信达金贸', '分段履约广州信达金贸'),
    2091047: ('万菱广场', '分段履约广州万菱广场'),
    2091314: ('白云绿地中心', '分段履约广州白云绿地中心'),
    2091349: ('中大附六院', '分段履约广州中大附属第六医院'),
    2091312: ('中大附三院', '分段履约广州中大附属第三医院'),
    2090185: ('珠江纺织城', '分段履约广州珠江国际纺织城'),
}
FULL_TO_SID = {v[1]: k for k, v in SID_MAP.items()}
SID_TO_SHORT = {k: v[0] for k, v in SID_MAP.items()}

def parse_date_col(c):
    """Parse column value like 20260601.0 -> '2026-06-01'"""
    if not isinstance(c, (int, float)):
        return None
    if pd.isna(c):
        return None
    ci = int(c)
    if 20260601 <= ci <= 20260731:
        return f'2026-{ci//10000:02d}-{(ci%10000)//100:02d}-{ci%100:02d}'
    return None

# --- Read Meituan orders ---
df_ord = pd.read_excel(MT_FILE, sheet_name=0, engine='calamine', header=0)
mt_orders = {}
for _, row in df_ord.iterrows():
    sid = int(row.iloc[1])
    if sid not in SID_TO_SHORT:
        continue
    for c in df_ord.columns:
        ds = parse_date_col(c)
        if ds:
            val = row[c]
            if pd.notna(val):
                mt_orders[(sid, ds)] = int(val)

# --- Read Meituan incentive ---
df_inc = pd.read_excel(MT_FILE, sheet_name=1, engine='calamine', header=0)
mt_incentive = {}
for _, row in df_inc.iterrows():
    sid = int(row.iloc[0])
    if sid not in SID_TO_SHORT:
        continue
    for c in df_inc.columns:
        ds = parse_date_col(c)
        if ds:
            val = row[c]
            if pd.notna(val):
                mt_incentive[(sid, ds)] = int(val)

# --- Build our data ---
our = {}
for date_dir in sorted(glob.glob(os.path.join(BASE_DIR, '26-06-*'))):
    dd = os.path.basename(date_dir)[-5:]
    ds = f'2026-{dd}'
    xls_files = glob.glob(os.path.join(date_dir, '*.xls')) + glob.glob(os.path.join(date_dir, '*.xlsx'))
    if not xls_files:
        continue
    df = pd.read_excel(max(xls_files, key=os.path.getmtime))
    df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

    for s in df['站点名称'].unique():
        sid = FULL_TO_SID.get(s)
        if not sid:
            continue
        sdf = df[df['站点名称'] == s]
        cnt = len(sdf)
        s_done = (sdf['物流单状态'] == '已送达').sum()
        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()

        rider_cols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rider_cols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders) or 0
        per_person = s_kpi_done / registered if registered > 0 else 0
        meets = per_person >= 20
        subsidy = (registered - 1) * 80 if meets else 0

        our[(sid, ds)] = dict(orders=cnt, done=s_done, kpi_done=s_kpi_done,
                              registered=registered, per_person=round(per_person, 1),
                              meets=meets, subsidy=subsidy)

# --- Compare ---
print('美团 vs 我方 - 人头激励对比 (2026年6月)')
print('美团激励 =(激励人数-1)x80 (推测) | 我方补贴 =(系统登记-1)x80, 条件人均(考核单量)>=20')
print()

# Header
hdr = f'{"日期":<12} {"站点":<10} {"美团单":>6} {"美激励":>6} {"美金":>7} {"我单":>5} {"考核":>5} {"登记":>4} {"人均":>5} {"达标":>4} {"我补贴":>7} {"差":>7}'
print(hdr)
print('-' * len(hdr))

total_mt = 0
total_our = 0
diffs = {}

all_keys = sorted(set(list(mt_orders.keys()) + list(mt_incentive.keys()) + list(our.keys())),
                  key=lambda x: (x[1], x[0]))

for sid, ds in all_keys:
    mt_ord = mt_orders.get((sid, ds), 0)
    mt_inc = mt_incentive.get((sid, ds))
    o = our.get((sid, ds))

    our_ord = o['orders'] if o else 0
    our_kpi = o['kpi_done'] if o else 0
    reg = o['registered'] if o else 0
    per_p = o['per_person'] if o else 0
    meets = o['meets'] if o else False
    our_sub = o['subsidy'] if o else 0

    mt_inc_n = mt_inc if mt_inc else 0
    mt_sub = (mt_inc_n - 1) * 80 if mt_inc_n > 1 else 0

    total_mt += mt_sub
    total_our += our_sub

    diff = our_sub - mt_sub
    diff_str = f'+{diff}' if diff > 0 else str(diff)

    if diff != 0:
        diffs[(sid, ds)] = diff
        flag = ' ***'
    else:
        flag = ''

    print(f'{ds:<12} {SID_TO_SHORT.get(sid, "?"):<10} {mt_ord:>6} {mt_inc_n:>6} {mt_sub:>7} {our_ord:>5} {our_kpi:>5} {reg:>4} {per_p:>5.1f} {"Y" if meets else "N":>4} {our_sub:>7} {diff_str:>7}{flag}')

print('-' * len(hdr))
print(f'美团激励合计: {total_mt:>8,}')
print(f'我方补贴合计: {total_our:>8,}')
print(f'差异:         {total_our - total_mt:>8,}')
print()
print(f'差异条目数: {len(diffs)}')
