"""万科欧泊 累计亏损 & 人均效率分析"""
import sys
sys.path.insert(0, '.')
from build_dashboard import get_station_histories
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

# 拉取所有站点历史
histories = get_station_histories()
data = histories.get('分段履约广州万科欧泊', [])

if not data:
    print("未找到万科欧泊数据")
    sys.exit(1)

# 解析数据
dates = []
orders = []
registered = []
per_person = []
profit = []
cumulative = []
running = 0
confirmed_count = 0

print(f"{'日期':<8} {'单量':>5} {'送达':>5} {'登记':>4} {'人均':>6} {'达标':>4} {'净利':>8} {'累计亏损':>10}")
print("-" * 58)

for d in data:
    dt = datetime.strptime(d['date_full'], '%Y-%m-%d')
    dates.append(dt)
    orders.append(d['done'])
    registered.append(d['registered'])
    pp = d['per']
    per_person.append(pp)

    profit_val = d['profit']
    profit.append(profit_val if profit_val is not None else 0)

    if profit_val is not None:
        running += profit_val
        confirmed_count += 1
    cumulative.append(running)

    meets = 'Y' if d['meets'] else 'N'
    profit_str = f"{profit_val:.0f}" if profit_val is not None else "—"
    print(f"{d['date']:<8} {d['orders']:>5} {d['done']:>5} {d['registered']:>4} {pp:>5.1f}  {meets:>4} {profit_str:>8} {running:>10.0f}")

print("-" * 58)
print(f"\n运营天数: {len(data)}天 (确认利润: {confirmed_count}天)")
print(f"累计亏损: {running:.0f} 元")
print(f"日均亏损: {running/confirmed_count:.0f} 元/天 (有利润数据的天数)")
print(f"日均单量: {np.mean(orders):.1f} 单/天 (已送达)")
avg_pp = np.mean([p for p in per_person if p > 0])
print(f"平均人效: {avg_pp:.1f} 单/人/天")
print(f"达标天数: {sum(1 for d in data if d['meets'])}/{len(data)}")

# ===== 图表 =====
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('万科欧泊 · 运营分析', fontsize=16, fontweight='bold')

# 1. 累计亏损线
ax1 = axes[0, 0]
colors = ['#e74c3c' if v <= 0 else '#27ae60' for v in cumulative]
ax1.fill_between(dates, cumulative, 0, alpha=0.15, color='#e74c3c')
ax1.plot(dates, cumulative, 'o-', color='#c0392b', linewidth=2, markersize=5, markerfacecolor='white')
ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
ax1.set_title('累计亏损', fontsize=13)
ax1.set_ylabel('元')
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
ax1.grid(True, alpha=0.3)

# 标注关键点
last = len(cumulative) - 1
ax1.annotate(f'{cumulative[last]:.0f}元', xy=(dates[last], cumulative[last]),
             xytext=(10, -15), textcoords='offset points', fontsize=9,
             color='#c0392b', fontweight='bold')

# 2. 日净利柱状图 (带补贴标注)
ax2 = axes[0, 1]
profits_arr = np.array(profit)
bars = ax2.bar(dates, profits_arr, width=0.7, color=['#e74c3c' if v <= 0 else '#27ae60' for v in profits_arr])
ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.8)
ax2.set_title('日净利', fontsize=13)
ax2.set_ylabel('元')
ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax2.xaxis.set_major_locator(mdates.DayLocator(interval=3))
ax2.grid(True, alpha=0.3, axis='y')

# 标记有补贴的日期
for i, d in enumerate(data):
    if d['meets']:
        subsidy = (d['registered'] - 1) * 80
        ax2.annotate(f"+{subsidy:.0f}", xy=(dates[i], profits_arr[i]),
                     xytext=(0, 8), textcoords='offset points', fontsize=7,
                     ha='center', color='#2980b9')

# 3. 人均效率 & 订单量
ax3 = axes[1, 0]
ax3.bar(dates, orders, width=0.7, color='#bdc3c7', alpha=0.6, label='送达单量')
ax3.set_ylabel('单量', color='#7f8c8d')
ax3.set_ylim(bottom=0)

ax3_twin = ax3.twinx()
ax3_twin.plot(dates, per_person, 's-', color='#2980b9', linewidth=2, markersize=6, markerfacecolor='white', label='人均单量')
ax3_twin.axhline(y=20, color='#e67e22', linestyle='--', linewidth=1, alpha=0.7, label='补贴线 20单')
ax3_twin.set_ylabel('人均单量', color='#2980b9')
ax3_twin.set_ylim(bottom=0)
ax3.set_title('订单量 & 人均效率', fontsize=13)
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
ax3.xaxis.set_major_locator(mdates.DayLocator(interval=3))

lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax3_twin.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)

# 4. 人员配置 vs 效率散点
ax4 = axes[1, 1]
for i, d in enumerate(data):
    size = d['done'] * 2 + 20
    color = '#27ae60' if d['meets'] else '#e74c3c'
    alpha = 0.7 if d['profit'] is not None else 0.3
    ax4.scatter(d['registered'], d['per'], s=size, c=color, alpha=alpha, edgecolors='white', linewidth=0.5)

ax4.axhline(y=20, color='#e67e22', linestyle='--', linewidth=1, alpha=0.7)
ax4.set_xlabel('系统登记人数')
ax4.set_ylabel('人均单量')
ax4.set_title('人员配置 · 效率分布\n(气泡=单量)', fontsize=13)
ax4.grid(True, alpha=0.3)

# 标注
for i, d in enumerate(data):
    if d['done'] >= 50 or d['per'] >= 25:
        ax4.annotate(d['date'], xy=(d['registered'], d['per']),
                     xytext=(5, 5), textcoords='offset points', fontsize=7)

plt.tight_layout()
plt.savefig('scripts/vanke_analysis.png', dpi=150, bbox_inches='tight')
print(f"\n图表已保存: scripts/vanke_analysis.png")

# 分阶段汇总
print("\n=== 分阶段汇总 ===")
print(f"{'阶段':<20} {'天数':>5} {'日均单量':>8} {'人均效率':>8} {'日均净利':>10} {'累计净利':>10}")

phases = [
    ("6/07-6/11 (2人期)", data[:5]),
    ("6/12-6/20 (过渡期)", data[5:13]),
    ("6/21-6/28 (冲刺期)", data[13:20]),
    ("6/29-7/02 (未确认期)", data[20:]),
]

for label, chunk in phases:
    if not chunk:
        continue
    n = len(chunk)
    avg_orders = np.mean([d['done'] for d in chunk])
    avg_per = np.mean([d['per'] for d in chunk if d['per'] > 0])
    profits_in_chunk = [d['profit'] for d in chunk if d['profit'] is not None]
    avg_profit = np.mean(profits_in_chunk) if profits_in_chunk else float('nan')
    cum_profit = sum(profits_in_chunk) if profits_in_chunk else float('nan')
    profit_str = f"{avg_profit:.0f}" if not np.isnan(avg_profit) else "—"
    cum_str = f"{cum_profit:.0f}" if not np.isnan(cum_profit) else "—"
    print(f"{label:<20} {n:>5} {avg_orders:>8.1f} {avg_per:>8.1f} {profit_str:>10} {cum_str:>10}")
