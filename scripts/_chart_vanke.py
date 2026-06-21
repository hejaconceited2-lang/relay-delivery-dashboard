import sys
sys.stdout.reconfigure(encoding='utf-8')

dates = ['06-07','06-08','06-09','06-10','06-11','06-12','06-13',
         '06-14','06-15','06-16','06-17','06-18','06-19','06-20','06-21']
orders = [26, 23, 21, 35, 35, 46, 43, 71, 40, 34, 30, 47, 47, 31, 49]
profits = [-182, -193, -200, -210, -151, -169, -256, -90, -246, -154, -168, -380, -109, -202, -292]

FULL = chr(9608)
LIGHT = chr(9618)

max_o = max(orders)
min_p = min(profits)
max_p = max(profits)
p_range = max_p - min_p
H = 16

print()
print('  万科欧泊  日单量 & 净利')
print('  ' + '=' * 79)
print()

# ====== Orders Bar ======
print('  单量')
for row in range(H, 0, -1):
    o_val = int(row / H * max_o)
    if row == H:
        line = f'{max_o:3d} '
    elif row == H // 2:
        line = f'{max_o // 2:3d} '
    elif row == 1:
        line = '  0 '
    else:
        line = '    '

    for o in orders:
        h = int(o / max_o * H)
        line += ' ██' if h >= row else '   '
    print(line)

print('    ' + ''.join(f' {d[3:]}' for d in dates))
print()

# ====== Profit Line (no connectors, just markers + value labels) ======
print('  净利 (¥)')
for row in range(H, 0, -1):
    p_val = int(min_p + (row - 1) / (H - 1) * p_range)
    line = f'{p_val:4d} '

    for p in profits:
        h = int((p - min_p) / p_range * (H - 1)) if p_range > 0 else 0
        if h == row - 1:
            line += '  ' + ('\033[91m●\033[0m' if p < -300 else '\033[91m○\033[0m' if p < -150 else '\033[93m○\033[0m')
        else:
            line += '   '
    print(line)

print('  ¥0 ' + '─' * 45)
print('    ' + ''.join(f' {d[3:]}' for d in dates))
print()

# ====== Table ======
print('  ' + '-' * 67)
print('  Date  ', end='')
for d in dates:
    print(f'  {d[3:]}', end='')
print()
print('  Orders', end='')
for o in orders:
    print(f'  {o:2d}', end='')
print()
print('  Profit', end='')
for p in profits:
    print(f' {p:4d}', end='')
print()
print('  ' + '-' * 67)
print()
print('  15日均 ¥-200  始终亏损  人力 ¥270/天 + 物料 ¥3.3/天')
print('  最好 06-14: 71单 ¥-90  (唯一触发补贴+¥160)')
print('  最差 06-18: 47单 ¥-380 (取消赔偿¥243)')
print()
print('  关键: 需 108单/天 覆盖人力成本, 当前最高仅71单')
