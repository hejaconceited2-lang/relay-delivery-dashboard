# -*- coding: utf-8 -*-
"""
珠江国际轻纺城 · 超长订单 & 取消订单分析
数据: 2026-06-17  |  输出到文件确保 UTF-8
"""
import pandas as pd
import numpy as np
from datetime import datetime
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(script_dir, 'zhujiang_analysis_report.txt')

lines = []

def p(s=""):
    lines.append(s)

INPUT = r"D:\CC\接力送日订单\26-06-17\[新]校园订单详情_20260617_213418_5.xls"

df = pd.read_excel(INPUT)
df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()
zj = df[df['站点名称'].str.contains('珠江国际轻纺城', na=False)].copy()

# Time parsing
zj['下单时间_dt'] = pd.to_datetime(zj['下单时间'], errors='coerce')
zj['送达时间_dt'] = pd.to_datetime(zj['送达时间'], errors='coerce')
zj['期望送达时间_dt'] = pd.to_datetime(zj['期望送达时间'], errors='coerce')

# Delivery duration
done_mask = zj['物流单状态'] == '已送达'
zj.loc[done_mask, '配送时长_min'] = (
    zj.loc[done_mask, '送达时间_dt'] - zj.loc[done_mask, '下单时间_dt']
).dt.total_seconds() / 60

# Rider count
rider_cols = ['经手骑手1', '经手骑手2', '经手骑手3', '经手骑手4', '经手骑手5']
zj['骑手人数'] = zj[rider_cols].notna().sum(axis=1)

# ================================================================
p("=" * 70)
p("  珠江国际轻纺城 · 2026-06-17 订单分析")
p("=" * 70)
p()

total = len(zj)
done = (zj['物流单状态'] == '已送达').sum()
canc = (zj['物流单状态'] == '已取消').sum()
p(f"总订单: {total}  已送达: {done}  已取消: {canc}  取消率: {canc/total*100:.1f}%")
p(f"编制: 3人  人均: {total/3:.1f}单  配送品类: {zj['配送品类'].unique().tolist()}")
p()

# ================================================================
# 一、已送达订单 · 配送时长分析
# ================================================================
p("=" * 70)
p("  一、已送达订单 · 配送时长分析 (n=36)")
p("=" * 70)
p()

times = zj.loc[done_mask, '配送时长_min'].dropna()
p(f"配送时长统计:")
p(f"  均值: {times.mean():.1f} min")
p(f"  中位: {times.median():.1f} min")
p(f"  最小: {times.min():.1f} min")
p(f"  最大: {times.max():.1f} min")
p(f"  标准差: {times.std():.1f} min")
p()

cv = times.std() / times.mean() * 100
if cv > 80:
    cv_label = "波动极大，存在严重异常值"
elif cv > 50:
    cv_label = "波动较大"
else:
    cv_label = "分布均匀"
p(f"  变异系数(CV): {cv:.1f}%  <- {cv_label}")
p()

# Distribution
bins = [(0, 15), (15, 30), (30, 45), (45, 60), (60, 90), (90, 999)]
for lo, hi in bins:
    cnt = ((times > lo) & (times <= hi)).sum()
    bar = '#' * max(1, int(cnt / done * 50))
    label = f'{lo}-{hi}min' if hi != 999 else f'>{lo}min'
    p(f"  {label:>12s}: {int(cnt):2d}单 ({cnt/done*100:4.1f}%) {bar}")

p()
p(f"  超30min: {int((times > 30).sum())}单 ({(times > 30).sum()/done*100:.1f}%)")
p(f"  超45min: {int((times > 45).sum())}单 ({(times > 45).sum()/done*100:.1f}%)")
p(f"  超60min: {int((times > 60).sum())}单 ({(times > 60).sum()/done*100:.1f}%)")
p(f"  超90min: {int((times > 90).sum())}单 ({(times > 90).sum()/done*100:.1f}%)")
p()

# ================================================================
# 二、超长订单明细 (>45min)
# ================================================================
LONG_THRESHOLD = 45
long_orders = zj[done_mask & (zj['配送时长_min'] > LONG_THRESHOLD)].sort_values('配送时长_min', ascending=False)
p("=" * 70)
p(f"  二、超长订单明细 (>{LONG_THRESHOLD}min, n={len(long_orders)})")
p("=" * 70)
p()

for i, (_, row) in enumerate(long_orders.iterrows()):
    dur = row['配送时长_min']
    p(f"--- #{i+1} · 配送 {dur:.0f}min ---")
    p(f"  订单号: {row['订单号']}")
    p(f"  下单:   {row['下单时间_dt'].strftime('%H:%M:%S')}")
    p(f"  送达:   {row['送达时间_dt'].strftime('%H:%M:%S')}")
    if pd.notna(row['期望送达时间_dt']):
        p(f"  期望送达: {row['期望送达时间_dt'].strftime('%H:%M:%S')}")
        delay = (row['送达时间_dt'] - row['期望送达时间_dt']).total_seconds() / 60
        if delay > 0:
            p(f"  超时期望 {delay:.0f}min !!")
    p(f"  配送品类: {row['配送品类']}")
    p(f"  送餐上楼: {row['送餐上楼单']}")
    p(f"  商家: {row['商家名']}")
    p(f"  骑手人数: {int(row['骑手人数'])}")

    rider_timeline = []
    for j in range(1, 6):
        rk = f'经手骑手{j}'
        tk = f'骑手{j}经手时间'
        if pd.notna(row.get(rk)) and pd.notna(row.get(tk)):
            rt = pd.to_datetime(row[tk])
            rider_timeline.append(f"骑手{j}={row[rk]}@{rt.strftime('%H:%M')}")
    if rider_timeline:
        p(f"  骑手时间线: {' -> '.join(rider_timeline)}")
    p()

# ================================================================
# 三、取消订单分析
# ================================================================
canc_orders = zj[zj['物流单状态'] == '已取消'].sort_values('下单时间_dt')
p("=" * 70)
p(f"  三、取消订单分析 (n={len(canc_orders)})")
p("=" * 70)
p()

# Hour distribution
p("按小时分布:")
for h in sorted(canc_orders['下单时间_dt'].dt.hour.dropna().unique()):
    cnt = (canc_orders['下单时间_dt'].dt.hour == h).sum()
    bar = '#' * cnt
    p(f"  {h:02d}:00-{h:02d}:59: {cnt}单 {bar}")
p()

# Detail per cancelled order
for i, (_, row) in enumerate(canc_orders.iterrows()):
    p(f"--- 取消 #{i+1} ---")
    p(f"  订单号: {row['订单号']}")
    p(f"  下单:   {row['下单时间_dt'].strftime('%H:%M:%S') if pd.notna(row['下单时间_dt']) else 'N/A'}")
    p(f"  期望送达: {row['期望送达时间_dt'].strftime('%H:%M:%S') if pd.notna(row['期望送达时间_dt']) else 'N/A'}")
    p(f"  配送品类: {row['配送品类']}")
    p(f"  送餐上楼: {row['送餐上楼单']}")
    p(f"  商家: {row['商家名']}")
    p(f"  订单实付: {row['订单实付']}元")
    p(f"  骑手人数: {int(row['骑手人数'])} (骑手途经次数)")

    rider_timeline = []
    for j in range(1, 6):
        rk = f'经手骑手{j}'
        tk = f'骑手{j}经手时间'
        if pd.notna(row.get(rk)) and pd.notna(row.get(tk)):
            rt = pd.to_datetime(row[tk])
            rider_timeline.append(f"骑手{j}={row[rk]}@{rt.strftime('%H:%M')}")
    if rider_timeline:
        p(f"  骑手时间线: {' -> '.join(rider_timeline)}")
    else:
        p(f"  骑手时间线: 无骑手经手记录（可能在骑手接单前取消）")

    if pd.notna(row.get('增值服务产品')) and str(row['增值服务产品']).strip():
        p(f"  增值服务: {row['增值服务产品']}")
    p()

# Cancel vs completed comparison
p("--- 取消 vs 已送达 对比 ---")
p()

p("取消订单商家分布:")
canc_merchants = canc_orders['商家名'].value_counts()
for m, c in canc_merchants.items():
    done_c = (zj.loc[done_mask, '商家名'] == m).sum()
    p(f"  {m}: 取消{c}单, 已送达{done_c}单, 取消率{c/(c+done_c)*100:.0f}%")

p()
p("配送品类分布:")
canc_cat = canc_orders['配送品类'].value_counts()
for m, c in canc_cat.items():
    done_c = (zj.loc[done_mask, '配送品类'] == m).sum()
    p(f"  {m}: 取消{c}单, 已送达{done_c}单")

p()
for lbl, subset in [('送餐上楼', '是'), ('不上楼', '否')]:
    canc_c = (canc_orders['送餐上楼单'] == subset).sum()
    done_c = (zj.loc[done_mask, '送餐上楼单'] == subset).sum()
    p(f"  {lbl}: 取消{canc_c}单, 已送达{done_c}单, 取消率{canc_c/(canc_c+done_c)*100:.0f}%")

p()
p("取消订单时段分析:")
for h in range(7, 20):
    canc_c = (canc_orders['下单时间_dt'].dt.hour == h).sum()
    done_c = (zj.loc[done_mask, '下单时间_dt'].dt.hour == h).sum()
    total_c = canc_c + done_c
    if total_c > 0:
        p(f"  {h:02d}:00: 取消{canc_c} 已送达{done_c} 取消率{canc_c/total_c*100:.0f}%")

# ================================================================
# 四、关键发现汇总
# ================================================================
p()
p("=" * 70)
p("  四、关键发现汇总")
p("=" * 70)
p()

if len(long_orders) > 0:
    long_times = long_orders['配送时长_min']
    normal_mask = done_mask & (zj['配送时长_min'] <= LONG_THRESHOLD)
    normal_times = zj.loc[normal_mask, '配送时长_min']
    p(f"1. 超长订单({LONG_THRESHOLD}min+)共{len(long_orders)}单, 正常订单{len(normal_times)}单")
    p(f"   超长订单平均配送: {long_times.mean():.0f}min")
    p(f"   正常订单平均配送: {normal_times.mean():.0f}min")
    p(f"   排除超长订单后整体均值: {normal_times.mean():.0f}min (原均值{times.mean():.0f}min)")
    p()

if canc/total > 0.1:
    cancel_verdict = "偏高，高于10%"
else:
    cancel_verdict = "正常"
p(f"2. 取消率 {canc/total*100:.1f}%, 12单取消 ({cancel_verdict})")

peak_canc_h = canc_orders['下单时间_dt'].dt.hour.value_counts().idxmax()
peak_canc_c = canc_orders['下单时间_dt'].dt.hour.value_counts().max()
p(f"3. 取消高峰: {int(peak_canc_h):02d}:00 ({int(peak_canc_c)}单)")

if '订单实付' in zj.columns:
    canc_avg = canc_orders['订单实付'].mean()
    done_avg = zj.loc[done_mask, '订单实付'].mean()
    p(f"4. 取消订单平均实付: {canc_avg:.1f}元, 已送达平均实付: {done_avg:.1f}元")

capacity_3h = 3 * 3 * 12
p(f"5. 3人×3h产能={capacity_3h}单, 实际{total}单, 产能利用率={total/capacity_3h*100:.0f}%")
p(f"   编制远超需求: 按12单/h, {total}单仅需{max(1, int(np.ceil(total/(3*12))))}人×3h")

p()
p("=" * 70)
p("  分析完成")
p(f"  输出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
p("=" * 70)

# Write to file
with open(OUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

# Also print to console (best effort)
for line in lines:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'))

print(f"\n[报告已保存] {OUT_FILE}")
