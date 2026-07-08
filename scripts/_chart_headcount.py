import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import os, glob, sys
sys.stdout.reconfigure(encoding='utf-8')

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

BASE = r'D:\CC\接力送日订单'
MT = os.path.join(BASE, '202606-艾云.xlsx')

df_mt = pd.read_excel(MT, sheet_name=0, engine='calamine', header=0)
ID_TO_NAME = {}
for _, row in df_mt.iterrows():
    ID_TO_NAME[int(row.iloc[1])] = row.iloc[2].replace('分段履约广州', '')

def pdate(c):
    if not isinstance(c, (int, float)) or pd.isna(c): return None
    ci = int(c)
    if 20260601 <= ci <= 20260630:
        return (2026, (ci % 10000) // 100, ci % 100)
    return None

df_inc = pd.read_excel(MT, sheet_name=1, engine='calamine', header=0)
mt = {}
for _, row in df_inc.iterrows():
    sid = int(row.iloc[0])
    if sid not in ID_TO_NAME: continue
    for c in df_inc.columns:
        dt = pdate(c)
        if dt and pd.notna(row[c]):
            mt[(sid, dt)] = int(row[c])

our_reg = {}
our_ord = {}
for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try:
        dt = (2026, int(parts[1]), int(parts[2]))
    except ValueError: continue
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()
    for s in df['站点名称'].unique():
        sids = df[df['站点名称'] == s]['站点ID'].dropna().unique()
        if not len(sids): continue
        sid = int(sids[0])
        if sid not in ID_TO_NAME: continue
        sdf = df[df['站点名称'] == s]
        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)
        s_kpi_done = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
        per_p = s_kpi_done / registered if registered > 0 else 0
        subsidy_count = (registered - 1) if per_p >= 20 and registered > 1 else 0
        our_reg[(sid, dt)] = subsidy_count
        our_ord[(sid, dt)] = len(sdf)

all_keys = set()
for k in mt: all_keys.add(k[1])
for k in our_reg: all_keys.add(k[1])
all_dates = sorted(all_keys)
date_labels = [f'{d[1]}/{d[2]:02d}' for d in all_dates]

# Active stations
station_volume = {}
for sid in ID_TO_NAME:
    total = sum(our_ord.get((sid, dt), 0) for dt in all_dates)
    station_volume[sid] = total
sorted_stations = sorted(ID_TO_NAME.keys(), key=lambda s: -station_volume[s])

active = []
for sid in sorted_stations:
    has = any(mt.get((sid, dt), 0) > 0 or our_reg.get((sid, dt), 0) > 0 for dt in all_dates)
    if has: active.append(sid)
station_labels = [ID_TO_NAME[s] for s in active]

# Build matrices
mt_matrix = np.zeros((len(active), len(all_dates)))
our_matrix = np.zeros((len(active), len(all_dates)))
ord_matrix = np.zeros((len(active), len(all_dates)))
for i, sid in enumerate(active):
    for j, dt in enumerate(all_dates):
        mt_matrix[i, j] = mt.get((sid, dt), 0)
        our_matrix[i, j] = our_reg.get((sid, dt), 0)
        ord_matrix[i, j] = our_ord.get((sid, dt), 0)

# Create figure
fig, axes = plt.subplots(2, 2, figsize=(28, 16))
fig.suptitle('美团激励人数 vs 我方补贴人数 · 2026年6月', fontsize=18, fontweight='bold', y=0.98)

# --- Panel 1: MT incentive headcount ---
ax1 = axes[0, 0]
im1 = ax1.imshow(mt_matrix, cmap='Blues', aspect='auto', vmin=0, vmax=max(mt_matrix.max(), 1))
ax1.set_xticks(range(len(date_labels)))
ax1.set_xticklabels(date_labels, rotation=90, fontsize=8)
ax1.set_yticks(range(len(station_labels)))
ax1.set_yticklabels(station_labels, fontsize=10)
for i in range(len(active)):
    for j in range(len(all_dates)):
        v = mt_matrix[i, j]
        if v > 0:
            ax1.text(j, i, int(v), ha='center', va='center', fontsize=8, fontweight='bold')
ax1.set_title('美团激励人数', fontsize=14, fontweight='bold')
plt.colorbar(im1, ax=ax1, shrink=0.8)

# --- Panel 2: Our subsidy headcount ---
ax2 = axes[0, 1]
im2 = ax2.imshow(our_matrix, cmap='Oranges', aspect='auto', vmin=0, vmax=max(our_matrix.max(), 1))
ax2.set_xticks(range(len(date_labels)))
ax2.set_xticklabels(date_labels, rotation=90, fontsize=8)
ax2.set_yticks(range(len(station_labels)))
ax2.set_yticklabels(station_labels, fontsize=10)
for i in range(len(active)):
    for j in range(len(all_dates)):
        v = our_matrix[i, j]
        if v > 0:
            ax2.text(j, i, int(v), ha='center', va='center', fontsize=8, fontweight='bold')
ax2.set_title('我方补贴人数 (登记-1, 人均≥20)', fontsize=14, fontweight='bold')
plt.colorbar(im2, ax=ax2, shrink=0.8)

# --- Panel 3: Difference (Our - MT) ---
ax3 = axes[1, 0]
diff_matrix = our_matrix - mt_matrix
vmax_diff = max(abs(diff_matrix.max()), abs(diff_matrix.min()), 1)
im3 = ax3.imshow(diff_matrix, cmap='RdBu_r', aspect='auto', vmin=-vmax_diff, vmax=vmax_diff)
ax3.set_xticks(range(len(date_labels)))
ax3.set_xticklabels(date_labels, rotation=90, fontsize=8)
ax3.set_yticks(range(len(station_labels)))
ax3.set_yticklabels(station_labels, fontsize=10)
for i in range(len(active)):
    for j in range(len(all_dates)):
        v = diff_matrix[i, j]
        if v != 0:
            ax3.text(j, i, f'{int(v):+d}', ha='center', va='center', fontsize=8, fontweight='bold',
                     color='white' if abs(v) > 3 else 'black')
ax3.set_title('差异 (我方 - 美团)', fontsize=14, fontweight='bold')
plt.colorbar(im3, ax=ax3, shrink=0.8)

# --- Panel 4: Bar chart summary ---
ax4 = axes[1, 1]
x = np.arange(len(active))
width = 0.35
mt_totals = [sum(mt.get((sid, dt), 0) for dt in all_dates) for sid in active]
our_totals = [sum(our_reg.get((sid, dt), 0) for dt in all_dates) for sid in active]
bars1 = ax4.bar(x - width/2, mt_totals, width, label='美团激励', color='#4A90D9', edgecolor='white')
bars2 = ax4.bar(x + width/2, our_totals, width, label='我方补贴', color='#E8843A', edgecolor='white')
for bar, v in zip(bars1, mt_totals):
    if v > 0:
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, str(v),
                 ha='center', fontsize=9, fontweight='bold')
for bar, v in zip(bars2, our_totals):
    if v > 0:
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, str(v),
                 ha='center', fontsize=9, fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels(station_labels, rotation=45, ha='right', fontsize=10)
ax4.set_title('月度激励人次合计对比', fontsize=14, fontweight='bold')
ax4.legend(fontsize=11)
ax4.set_ylabel('人次', fontsize=11)

plt.tight_layout(rect=[0, 0, 1, 0.95])
outpath = os.path.join(BASE, 'output', 'incentive_comparison.png')
os.makedirs(os.path.dirname(outpath), exist_ok=True)
plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Saved: {outpath}')
