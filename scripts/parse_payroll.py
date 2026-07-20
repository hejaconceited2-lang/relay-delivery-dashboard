"""
计薪表解析: 从接力送计薪表格.xlsx 提取每日实际人力成本和人数
"""
import sys
import io
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import os, re
from datetime import datetime, timedelta

def excel_serial_to_date(serial):
    return datetime(1899, 12, 30) + timedelta(days=int(serial))

def parse_date(val):
    if pd.isna(val): return None
    if isinstance(val, datetime): return val
    if isinstance(val, (int, float)) and 46000 < val < 47000:
        return excel_serial_to_date(int(val))
    if isinstance(val, str):
        s = val.strip()
        # Strip Chinese weekday suffix
        s = re.sub(r'(星期一|星期二|星期三|星期四|星期五|星期六|星期日|周一|周二|周三|周四|周五|周六|周日).*$', '', s)
        for fmt in ['%Y/%m/%d', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']:
            try: return datetime.strptime(s.strip(), fmt)
            except: pass
    return None

# Sheet名 → 站点全名
SHEET_MAP = {
    '番禺万科欧泊': '分段履约广州万科欧泊',
    '中大附属第六医院': '分段履约广州中大附属第六医院',
    '番禺万达': None, '北京路广百': None,
    '汇德国际': '分段履约广州汇德国际',
    '金鹰大厦': '分段履约广州金鹰大厦',
    '万菱广场': '分段履约广州万菱广场',
    '华林国际C馆': '分段履约广州华林国际C馆',
    '和业广场': '分段履约广州和业广场',
    '中大附三岭南医院': '分段履约广州中大附三岭南医院',
    '广州交易广场': '分段履约广州交易广场',
    '中大附属第三医院': '分段履约广州中大附属第三医院',
    '敏捷上城国际': '分段履约广州上城敏捷',
}

SKIP_NAMES = {'人员', '薪资', '合计', 'nan', '', '申请中', '已结清', '已申请', '上午', '下午'}

def parse_single_sheet(df, station):
    """解析单个子表, 返回 (daily_labor, daily_headcount)"""
    daily_labor = {}
    daily_headcount = {}

    # 1. 找所有日期单元格 → 同时按列分组，找出每个日期在同列的下一个日期
    date_cells = []  # [(row, col, datetime)]
    for r in range(len(df)):
        for c in range(df.shape[1]):
            dt = parse_date(df.iloc[r, c])
            if dt and dt.year == 2026:
                date_cells.append((r, c, dt))

    # 按列构建 (col) → [(row, dt)] 用于找"下一个日期"
    col_dates = {}
    for r, c, dt in date_cells:
        col_dates.setdefault(c, []).append((r, dt))
    for c in col_dates:
        col_dates[c].sort(key=lambda x: x[0])

    # 所有含日期的行号，用于跨block边界检测
    date_rows = set(r for r, c, dt in date_cells)

    # 2. 对每个日期, 向下扫描直到同列的下一个日期行（或 EOF）
    for r_date, c_date, dt in date_cells:
        date_str = dt.strftime('%Y-%m-%d')
        total_salary = 0
        names = []

        # 找同列的下一个日期行作为扫描上限
        next_date_row = len(df)
        same_col = col_dates.get(c_date, [])
        for r_next, _ in same_col:
            if r_next > r_date:
                next_date_row = r_next
                break

        # 扫描：从日期行下一行到下个日期行之前
        for row in range(r_date + 1, next_date_row):
            # 跨block边界检测：遇到其他日期行（上下层列偏移产生的序列号日期）停止
            if row in date_rows:
                break

            name_val = df.iloc[row, c_date]
            salary_val = df.iloc[row, c_date + 1]

            if pd.isna(name_val) or pd.isna(salary_val):
                continue

            # 跳过数字名（合计行的 0 标记等）
            if isinstance(name_val, (int, float)):
                continue

            name_s = str(name_val).strip()
            if not name_s or name_s in SKIP_NAMES or name_s.startswith('Unnamed'):
                continue
            if '物料保管' in name_s:
                continue
            if '合计' in name_s:
                continue

            if isinstance(salary_val, datetime):
                continue
            try:
                sal = float(salary_val)
                if sal >= 45:
                    total_salary += sal
                    names.append(name_s)
            except (ValueError, TypeError):
                pass

        if total_salary > 0:
            daily_labor.setdefault(date_str, {})[station] = int(total_salary)
            daily_headcount.setdefault(date_str, {})[station] = len(names)

    return daily_labor, daily_headcount


def parse_payroll(filepath):
    """解析计薪表, 返回 (daily_labor, actual_staff_overrides, actual_staff)"""
    daily_labor = {}
    daily_headcount = {}

    xls = pd.ExcelFile(filepath, engine='calamine')

    for sheet_name in xls.sheet_names:
        station = SHEET_MAP.get(sheet_name)
        if station is None:
            continue
        df = pd.read_excel(xls, sheet_name=sheet_name, engine='calamine', header=None)
        dl, dh = parse_single_sheet(df, station)

        # 合并到全局（同站点多个sheet时累加）
        for d, ss in dl.items():
            target = daily_labor.setdefault(d, {})
            for st, v in ss.items():
                target[st] = target.get(st, 0) + v
        for d, ss in dh.items():
            target = daily_headcount.setdefault(d, {})
            for st, v in ss.items():
                target[st] = target.get(st, 0) + v

    # 构建 actual_staff (取每个站点的最常见人数)
    actual_staff = {}
    for station in set().union(*(d.keys() for d in daily_headcount.values())):
        counts = {}
        for d, ss in daily_headcount.items():
            if station in ss:
                c = ss[station]
                counts[c] = counts.get(c, 0) + 1
        # 取出现最多的天数对应的人数
        actual_staff[station] = max(counts, key=counts.get)

    return daily_labor, daily_headcount, actual_staff


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '接力送真实人力计薪/接力送计薪表格.xlsx'
    labor, hc, staff = parse_payroll(path)

    print(f'=== DAILY_LABOR_COST ({len(labor)} dates) ===')
    for d in sorted(labor):
        for st, v in labor[d].items():
            short = st.replace('分段履约广州', '')
            print(f'  {d} {short}: ¥{v} ({hc.get(d,{}).get(st,"?")}人)')

    print(f'\n=== ACTUAL_STAFF ({len(staff)} stations) ===')
    for k, v in sorted(staff.items()):
        print(f'  {k.replace("分段履约广州","")}: {v}人')
