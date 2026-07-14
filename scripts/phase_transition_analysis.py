"""
接力送 · 各点位 Phase 1→2 过渡分析
分析每个点位从第一天运营后两周，骑手费从1元涨到2元时订单量的变化
"""
import sys, os, glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def find_xls(date_dir):
    candidates = glob.glob(os.path.join(date_dir, '*.xls')) + glob.glob(os.path.join(date_dir, '*.xlsx'))
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]

def main():
    # 收集所有日期的站点数据
    station_daily = defaultdict(dict)  # station -> {date_str: order_count}

    import re
    date_pattern = re.compile(r'^26-(0[6-9]|1[0-2])-\d{2}$')
    all_dirs = sorted(glob.glob(os.path.join(BASE_DIR, '26-0[6-9]-*')) +
                      glob.glob(os.path.join(BASE_DIR, '26-1[0-2]-*')))
    date_dirs = [d for d in all_dirs if date_pattern.match(os.path.basename(d))]

    print(f"扫描 {len(date_dirs)} 个日期目录...")

    for dd in date_dirs:
        date_str = '20' + os.path.basename(dd).replace('-', '-')
        xls_path = find_xls(dd)
        if not xls_path:
            continue

        try:
            df = pd.read_excel(xls_path)
            df = df[df['站点名称'].str.contains('分段履约', na=False)].copy()
        except Exception as e:
            print(f"  跳过 {date_str}: {e}")
            continue

        counts = df['站点名称'].value_counts()
        for station, cnt in counts.items():
            short_name = station.replace('分段履约广州', '')
            station_daily[short_name][date_str] = cnt

    print(f"\n共 {len(station_daily)} 个站点有数据\n")
    print("=" * 130)

    results = []

    for station in sorted(station_daily.keys()):
        days = sorted(station_daily[station].keys())
        if len(days) < 3:
            continue

        first_day = datetime.strptime(days[0], '%Y-%m-%d')
        transition_day = first_day + timedelta(days=14)  # 两周后

        # 分阶段：Phase 1 = 前14天（含第14天），Phase 2 = 第15天起
        phase1_days = [d for d in days if datetime.strptime(d, '%Y-%m-%d') <= transition_day]
        phase2_days = [d for d in days if datetime.strptime(d, '%Y-%m-%d') > transition_day]

        if not phase1_days:
            continue

        p1_orders = [station_daily[station][d] for d in phase1_days]
        p2_orders = [station_daily[station][d] for d in phase2_days] if phase2_days else []

        p1_avg = np.mean(p1_orders)
        p2_avg = np.mean(p2_orders) if p2_orders else None

        p1_median = np.median(p1_orders)
        p2_median = np.median(p2_orders) if p2_orders else None

        if p2_avg is not None:
            drop_pct = (1 - p2_avg / p1_avg) * 100
        else:
            drop_pct = None

        total_days = len(days)
        has_phase2 = len(phase2_days) > 0

        results.append({
            'station': station,
            'first_day': days[0],
            'transition': transition_day.strftime('%Y-%m-%d'),
            'total_days': total_days,
            'p1_days': len(phase1_days),
            'p2_days': len(phase2_days),
            'p1_avg': p1_avg,
            'p2_avg': p2_avg,
            'p1_median': p1_median,
            'p2_median': p2_median,
            'p1_max': max(p1_orders),
            'p2_max': max(p2_orders) if p2_orders else None,
            'p1_min': min(p1_orders),
            'p2_min': min(p2_orders) if p2_orders else None,
            'drop_pct': drop_pct,
            'has_phase2': has_phase2,
            'p1_list': p1_orders,
            'p2_list': p2_orders,
        })

    # 排序：有Phase2数据的排前面，按跌幅排序
    results.sort(key=lambda r: (
        not r['has_phase2'],
        r['drop_pct'] if r['drop_pct'] is not None else 999
    ))

    print(f"{'站点':<16} {'首日':>10} {'过渡日':>10} {'总天数':>6} {'P1天':>5} {'P2天':>5} "
          f"{'P1日均':>7} {'P2日均':>7} {'跌幅':>7} {'P1区间':>16} {'P2区间':>16}")
    print("-" * 130)

    for r in results:
        p2_avg_str = f"{r['p2_avg']:.0f}" if r['p2_avg'] is not None else 'N/A'
        drop_str = f"{r['drop_pct']:.0f}%" if r['drop_pct'] is not None else 'N/A'
        p1_range = f"{r['p1_min']}-{r['p1_max']}"
        p2_range = f"{r['p2_min']}-{r['p2_max']}" if r['p2_max'] is not None else 'N/A'

        marker = ' ← 未到过渡期' if not r['has_phase2'] else ''

        print(f"{r['station']:<16} {r['first_day']:>10} {r['transition']:>10} {r['total_days']:>6} "
              f"{r['p1_days']:>5} {r['p2_days']:>5} {r['p1_avg']:>7.0f} {p2_avg_str:>7} "
              f"{drop_str:>7} {p1_range:>16} {p2_range:>16}{marker}")

    # 汇总统计
    print("\n" + "=" * 130)
    print("\n=== 汇总 ===")

    phase2_results = [r for r in results if r['has_phase2']]
    phase1_only = [r for r in results if not r['has_phase2']]

    print(f"\n已进入Phase 2的站点: {len(phase2_results)} 个")
    print(f"尚未到过渡期的站点: {len(phase1_only)} 个")

    if phase2_results:
        drops = [r['drop_pct'] for r in phase2_results if r['drop_pct'] is not None]
        print(f"\nPhase 1→2 订单量跌幅:")
        print(f"  中位跌幅: {np.median(drops):.0f}%")
        print(f"  平均跌幅: {np.mean(drops):.0f}%")
        print(f"  最大跌幅: {max(drops):.0f}% ({[r['station'] for r in phase2_results if r['drop_pct'] == max(drops)][0]})")
        print(f"  最小跌幅: {min(drops):.0f}% ({[r['station'] for r in phase2_results if r['drop_pct'] == min(drops)][0]})")

        print(f"\nPhase 1 日均单量: {np.mean([r['p1_avg'] for r in phase2_results]):.0f}")
        print(f"Phase 2 日均单量: {np.mean([r['p2_avg'] for r in phase2_results]):.0f}")

        # 单个站点详情
        print("\n\n=== 各站点逐日详情 ===\n")
        for r in phase2_results:
            print(f"\n【{r['station']}】首日{r['first_day']}，过渡日{r['transition']}")
            print(f"  Phase 1 ({r['p1_days']}天): 日均{r['p1_avg']:.0f}单, 中位{r['p1_median']:.0f}, 区间[{r['p1_min']}-{r['p1_max']}]")
            if r['p2_days'] > 0:
                print(f"  Phase 2 ({r['p2_days']}天): 日均{r['p2_avg']:.0f}单, 中位{r['p2_median']:.0f}, 区间[{r['p2_min']}-{r['p2_max']}]")
                print(f"  跌幅: {r['drop_pct']:.0f}%")
                # 日均变化
                p1_daily = r['p1_list']
                p2_daily = r['p2_list']
                print(f"  P1逐日: {', '.join(str(int(x)) for x in p1_daily)}")
                print(f"  P2逐日: {', '.join(str(int(x)) for x in p2_daily)}")

    # 尚未到过渡期的站点
    if phase1_only:
        print(f"\n\n=== 尚未到过渡期的站点 ===\n")
        for r in phase1_only:
            print(f"  {r['station']}: 首日{r['first_day']}, 过渡日{r['transition']}, "
                  f"当前{r['p1_days']}天, 日均{r['p1_avg']:.0f}单")

    return results

if __name__ == '__main__':
    results = main()
