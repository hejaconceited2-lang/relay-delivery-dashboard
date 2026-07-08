"""合并美团+我方激励表, 生成对比Excel+图表"""
import pandas as pd
import os, glob, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False
sys.stdout.reconfigure(encoding='utf-8')

BASE = r'D:\CC\接力送日订单'
MT_FILE = os.path.join(BASE, '202606-艾云.xlsx')
OUT_XLSX = os.path.join(BASE, 'output', '激励对比_2026年6月.xlsx')
OUT_PNG = os.path.join(BASE, 'output', '激励对比_2026年6月.png')

EXCLUDE = {'新亚洲电子城', '孙逸仙北院', '新中国大厦'}

# ========== 1. Read MT ==========
df_mt_raw = pd.read_excel(MT_FILE, sheet_name=1, engine='calamine', header=0)
mt_data = {}  # {sid: {day: people}}
mt_sid_name = {}
for _, row in df_mt_raw.iterrows():
    sid = int(row.iloc[0])
    sname = row.iloc[1].replace('分段履约广州', '')
    if sname in EXCLUDE: continue
    mt_sid_name[sid] = sname
    mt_data[sid] = {}
    for c in df_mt_raw.columns[2:-1]:
        if pd.notna(row[c]):
            day = int(str(int(c))[-2:])
            mt_data[sid][day] = int(row[c])

# ========== 2. Read our data ==========
our_data = {}  # {sid: {day: people}}
our_sid_name = {}
our_has_order = {}

for ddir in sorted(glob.glob(os.path.join(BASE, '26-06-*'))):
    dd = os.path.basename(ddir)
    parts = dd.split('-')
    if len(parts) != 3: continue
    try: day = int(parts[2])
    except ValueError: continue
    fs = glob.glob(os.path.join(ddir, '*.xls')) + glob.glob(os.path.join(ddir, '*.xlsx'))
    if not fs: continue
    df = pd.read_excel(max(fs, key=os.path.getmtime))
    mask = df['站点名称'].astype(str).str.contains('分段履约', na=False)
    df = df[mask].copy()
    for s in df['站点名称'].unique():
        short = s.replace('分段履约广州', '')
        if short in EXCLUDE: continue
        sdf = df[df['站点名称'] == s]
        sids = sdf['站点ID'].dropna().unique()
        if not len(sids): continue
        sid = int(sids[0])
        our_sid_name[sid] = short
        if sid not in our_data: our_data[sid] = {}
        if sid not in our_has_order: our_has_order[sid] = set()
        our_has_order[sid].add(day)

        rcols = [c for c in df.columns if c.startswith('经手骑手') and c != '经手骑手1']
        riders = set()
        for col in rcols:
            if col in df.columns:
                for r in sdf[col].dropna():
                    riders.add(str(r).strip())
        registered = len(riders)
        if registered > 1:
            s_kpi = ((sdf['物流单状态'] == '已送达') & (sdf['商家ID'].astype(float) != -1)).sum()
            if s_kpi / registered >= 20:
                our_data[sid][day] = registered - 1

# ========== 3. Build unified station list ==========
all_sids = sorted(set(list(mt_data.keys()) + list(our_data.keys())))
station_names = {}
for sid in all_sids:
    station_names[sid] = our_sid_name.get(sid, mt_sid_name.get(sid, str(sid)))

# ========== 4. Write Excel ==========
with pd.ExcelWriter(OUT_XLSX, engine='openpyxl') as writer:
    # Sheet 1: MT
    rows_mt = []
    for sid in all_sids:
        row = {'站点ID': sid, '站点名称': f'分段履约广州{station_names[sid]}'}
        total = 0
        for d in range(1, 31):
            v = mt_data.get(sid, {}).get(d, None)
            row[f'202606{d:02d}'] = v
            total += (v or 0)
        row['合计'] = total
        rows_mt.append(row)
    df_mt = pd.DataFrame(rows_mt)
    cols = ['站点ID', '站点名称'] + [f'202606{d:02d}' for d in range(1,31)] + ['合计']
    df_mt = df_mt[cols]
    df_mt.to_excel(writer, sheet_name='美团-人头激励', index=False)

    # Sheet 2: Our
    rows_our = []
    for sid in all_sids:
        row = {'站点ID': sid, '站点名称': f'分段履约广州{station_names[sid]}'}
        total = 0
        for d in range(1, 31):
            v = our_data.get(sid, {}).get(d, None)
            has_ord = d in our_has_order.get(sid, set())
            if v is not None and v > 0:
                row[f'202606{d:02d}'] = v
            elif has_ord:
                row[f'202606{d:02d}'] = 0
            else:
                row[f'202606{d:02d}'] = None
            total += (v or 0)
        row['合计'] = total
        rows_our.append(row)
    df_our = pd.DataFrame(rows_our)
    df_our = df_our[cols]
    df_our.to_excel(writer, sheet_name='我方-人头激励', index=False)

    # Sheet 3: Diff
    rows_diff = []
    for sid in all_sids:
        row = {'站点ID': sid, '站点名称': f'分段履约广州{station_names[sid]}'}
        total = 0
        for d in range(1, 31):
            m = mt_data.get(sid, {}).get(d, 0) or 0
            o = our_data.get(sid, {}).get(d, 0) or 0
            diff = o - m
            row[f'202606{d:02d}'] = diff if diff != 0 else 0
            total += diff
        row['合计'] = total
        rows_diff.append(row)
    df_diff = pd.DataFrame(rows_diff)
    df_diff = df_diff[cols]
    df_diff.to_excel(writer, sheet_name='差异(我方-美团)', index=False)

    # Sheet 4: Summary
    rows_sum = []
    for sid in all_sids:
        mt_total = sum(v for v in mt_data.get(sid, {}).values())
        our_total = sum(v for v in our_data.get(sid, {}).values())
        rows_sum.append({
            '站点': station_names[sid], '美团合计': mt_total, '我方合计': our_total,
            '差异': our_total - mt_total
        })
    df_sum = pd.DataFrame(rows_sum)
    df_sum = df_sum.sort_values('我方合计', ascending=False)
    # Totals row
    totals = {'站点': '合计', '美团合计': df_sum['美团合计'].sum(),
              '我方合计': df_sum['我方合计'].sum(), '差异': df_sum['差异'].sum()}
    df_sum = pd.concat([df_sum, pd.DataFrame([totals])], ignore_index=True)
    df_sum.to_excel(writer, sheet_name='汇总对比', index=False)

# ========== 5. Generate chart ==========
fig, axes = plt.subplots(2, 2, figsize=(26, 14))
fig.suptitle('美团激励 vs 我方补贴 人数对比 · 2026年6月', fontsize=18, fontweight='bold', y=0.98)

# Get stations sorted by our total
active_sids = [s for s in all_sids if sum(our_data.get(s, {}).values()) + sum(mt_data.get(s, {}).values()) > 0]
active_sids.sort(key=lambda s: -sum(our_data.get(s, {}).values()))
names = [station_names[s] for s in active_sids]
days = list(range(7, 31))  # Only 6/7 to 6/30

# --- Panel 1: MT heatmap ---
mt_mat = np.zeros((len(active_sids), len(days)))
for i, sid in enumerate(active_sids):
    for j, d in enumerate(days):
        mt_mat[i, j] = mt_data.get(sid, {}).get(d, 0)
ax1 = axes[0, 0]
im1 = ax1.imshow(mt_mat, cmap='Blues', aspect='auto', vmin=0, vmax=max(mt_mat.max(), 1))
ax1.set_xticks(range(len(days))); ax1.set_xticklabels([f'{d}' for d in days], fontsize=8)
ax1.set_yticks(range(len(names))); ax1.set_yticklabels(names, fontsize=10)
for i in range(len(active_sids)):
    for j in range(len(days)):
        v = mt_mat[i, j]
        if v > 0: ax1.text(j, i, int(v), ha='center', va='center', fontsize=7, fontweight='bold')
ax1.set_title('美团激励人数', fontsize=14, fontweight='bold')
plt.colorbar(im1, ax=ax1, shrink=0.8)

# --- Panel 2: Our heatmap ---
our_mat = np.zeros((len(active_sids), len(days)))
for i, sid in enumerate(active_sids):
    for j, d in enumerate(days):
        our_mat[i, j] = our_data.get(sid, {}).get(d, 0)
ax2 = axes[0, 1]
im2 = ax2.imshow(our_mat, cmap='Oranges', aspect='auto', vmin=0, vmax=max(our_mat.max(), 1))
ax2.set_xticks(range(len(days))); ax2.set_xticklabels([f'{d}' for d in days], fontsize=8)
ax2.set_yticks(range(len(names))); ax2.set_yticklabels(names, fontsize=10)
for i in range(len(active_sids)):
    for j in range(len(days)):
        v = our_mat[i, j]
        if v > 0: ax2.text(j, i, int(v), ha='center', va='center', fontsize=7, fontweight='bold')
ax2.set_title('我方补贴人数', fontsize=14, fontweight='bold')
plt.colorbar(im2, ax=ax2, shrink=0.8)

# --- Panel 3: Diff heatmap ---
diff_mat = our_mat - mt_mat
vmax_d = max(abs(diff_mat.max()), abs(diff_mat.min()), 1)
ax3 = axes[1, 0]
im3 = ax3.imshow(diff_mat, cmap='RdBu_r', aspect='auto', vmin=-vmax_d, vmax=vmax_d)
ax3.set_xticks(range(len(days))); ax3.set_xticklabels([f'{d}' for d in days], fontsize=8)
ax3.set_yticks(range(len(names))); ax3.set_yticklabels(names, fontsize=10)
for i in range(len(active_sids)):
    for j in range(len(days)):
        v = diff_mat[i, j]
        if v != 0:
            ax3.text(j, i, f'{int(v):+d}', ha='center', va='center', fontsize=7, fontweight='bold',
                     color='white' if abs(v) > 3 else 'black')
ax3.set_title('差异 (我方 - 美团)', fontsize=14, fontweight='bold')
plt.colorbar(im3, ax=ax3, shrink=0.8)

# --- Panel 4: Bar chart ---
ax4 = axes[1, 1]
x = np.arange(len(active_sids))
w = 0.35
mt_tt = [sum(mt_data.get(s, {}).values()) for s in active_sids]
our_tt = [sum(our_data.get(s, {}).values()) for s in active_sids]
bars_mt = ax4.barh(x - w/2, mt_tt, w, label='美团激励', color='#4A90D9')
bars_our = ax4.barh(x + w/2, our_tt, w, label='我方补贴', color='#E8843A')
for i, (m, o) in enumerate(zip(mt_tt, our_tt)):
    if m > 0: ax4.text(m + 0.5, i - w/2, str(m), va='center', fontsize=8, fontweight='bold')
    if o > 0: ax4.text(o + 0.5, i + w/2, str(o), va='center', fontsize=8, fontweight='bold')
ax4.set_yticks(x); ax4.set_yticklabels(names, fontsize=10)
ax4.set_xlabel('人次', fontsize=11)
ax4.set_title('月度激励人次合计', fontsize=14, fontweight='bold')
ax4.legend(fontsize=11, loc='lower right')
ax4.invert_yaxis()

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.savefig(OUT_PNG, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()

print(f'Excel: {OUT_XLSX}')
print(f'Chart: {OUT_PNG}')
print(f'MT total: {df_sum.iloc[-2]["美团合计"]:.0f}')
print(f'Our total: {df_sum.iloc[-2]["我方合计"]:.0f}')
print(f'Diff: {df_sum.iloc[-2]["差异"]:.0f}')
