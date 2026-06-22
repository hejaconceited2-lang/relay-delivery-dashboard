import pandas as pd
import glob, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = r'D:\CC\接力送日订单'

date_dirs = sorted(
    d for d in os.listdir(BASE)
    if len(d) == 8 and d[2] == '-' and d[5] == '-' and os.path.isdir(os.path.join(BASE, d))
)

print('=' * 80)
print('接力送 · 全量数据自检')
print('=' * 80)

all_issues = []
daily_stats = []

for dd in date_dirs:
    candidates = glob.glob(os.path.join(BASE, dd, '*.xls*'))
    if not candidates:
        print(f'\n[{dd}] 跳过：无数据文件')
        continue

    df = pd.read_excel(candidates[0])
    df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()

    total = len(df)
    done = (df['物流单状态'] == '已送达').sum()
    canc = (df['物流单状态'] == '已取消').sum()
    pickup = (df['物流单状态'] == '已取货').sum()
    stations = df['站点名称'].nunique()

    # 找出经手骑手列
    rider_cols = [c for c in df.columns if '经手骑手' in c]
    rider1_col = rider_cols[0] if rider_cols else None
    rider2plus = rider_cols[1:] if len(rider_cols) > 1 else []

    total_staff = 0
    station_lines = []

    for s in df['站点名称'].unique():
        sdf = df[df['站点名称'] == s]
        cnt = len(sdf)
        s_done = (sdf['物流单状态'] == '已送达').sum()
        s_canc = (sdf['物流单状态'] == '已取消').sum()

        riders = set()
        for col in rider2plus:
            for r in sdf[col].dropna():
                riders.add(str(r).strip())
        staff = len(riders)
        total_staff += staff

        riders1 = set()
        if rider1_col:
            for r in sdf[rider1_col].dropna():
                riders1.add(str(r).strip())

        short = s.replace('分段履约广州', '')
        pp = f'{cnt/staff:.1f}' if staff > 0 else 'N/A'
        flags = []

        if cnt > 0 and staff == 0:
            flags.append('编制=0')
        if staff > 0 and cnt / staff > 100:
            flags.append(f'人效{cnt/staff:.0f}(偏高)')
        if s_done > 0 and len(riders1) == 0:
            flags.append('无一段骑手')
        if cnt > 0 and s_canc / cnt > 0.3:
            flags.append(f'取消率{s_canc/cnt*100:.0f}%')
        if staff > 0 and cnt / staff < 5:
            flags.append(f'人效{cnt/staff:.1f}(偏低)')

        for f in flags:
            all_issues.append(f'[{dd}] {short}: {f}')

        flag_str = ' ⚠' + ','.join(flags) if flags else ''
        station_lines.append(f'  {short:<16s} {cnt:3d}单  编制{staff}人  人均{pp:>5s}  完成{s_done}  取消{s_canc}  一段{len(riders1)}人{flag_str}')

    daily_stats.append({
        'date': dd, 'orders': total, 'stations': stations,
        'done': done, 'canc': canc, 'pickup': pickup, 'total_staff': total_staff,
    })

    date_label = f'20{dd[0:2]}-{dd[3:5]}-{dd[6:8]}'
    print(f'\n-- {date_label} -- {total}单 / {stations}站 / 编制{total_staff}人 --')
    for line in station_lines:
        print(line)

# 汇总
print('\n' + '=' * 80)
print('汇总')
print('=' * 80)
total_orders = sum(d['orders'] for d in daily_stats)
total_done = sum(d['done'] for d in daily_stats)
total_canc = sum(d['canc'] for d in daily_stats)
n_days = len(daily_stats)
print(f'累计: {total_orders}单 / {n_days}天 / 完成{total_done} / 取消{total_canc}')
print(f'完成率: {total_done/total_orders*100:.1f}%')
print(f'日均: {total_orders/n_days:.0f}单/天')

print(f'\n-- 异常项 ({len(all_issues)}条) --')
if all_issues:
    for iss in all_issues:
        print(f'  ⚠ {iss}')
else:
    print('  无异常')

print(f'\n-- 逐日趋势 --')
print(f'{"日期":>12s} | {"单量":>4s} | {"站数":>3s} | {"编制":>4s} | {"完成":>5s} | {"取消":>4s} | {"配送中":>5s}')
for ds in daily_stats:
    d = f'20{ds["date"][0:2]}-{ds["date"][3:5]}-{ds["date"][6:8]}'
    print(f'  {d} | {ds["orders"]:4d} | {ds["stations"]:2d}  | {ds["total_staff"]:3d}  | {ds["done"]:4d} | {ds["canc"]:3d} | {ds["pickup"]:4d}')

print(f'\n-- 站点出现天数 --')
station_days = {}
for dd in date_dirs:
    candidates = glob.glob(os.path.join(BASE, dd, '*.xls*'))
    if not candidates: continue
    df = pd.read_excel(candidates[0])
    df = df[df['站点名称'].str.contains('分段履约', na=False)]
    for s in df['站点名称'].unique():
        short = s.replace('分段履约广州', '')
        station_days[short] = station_days.get(short, 0) + 1
for s, days in sorted(station_days.items(), key=lambda x: x[1], reverse=True):
    print(f'  {s:<16s} {days}天')

print('\n自检完成.')
