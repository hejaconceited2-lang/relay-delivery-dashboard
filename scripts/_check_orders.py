import xlrd, sys
sys.stdout.reconfigure(encoding='utf-8')

wb = xlrd.open_workbook(r'D:\CC\接力送日订单\26-07-07\[新]校园订单详情_20260707_143528_0.xls')
sh = wb.sheet_by_index(0)

orders = []
for r in range(1, sh.nrows):
    station = str(sh.cell_value(r, 13))
    if '汇德' in station:
        order_id = str(int(sh.cell_value(r, 1))) if sh.cell_value(r, 1) else ''
        merchant_id = sh.cell_value(r, 3)
        merchant = str(sh.cell_value(r, 4))
        order_type = str(sh.cell_value(r, 5))
        status = str(sh.cell_value(r, 6))
        order_time = str(sh.cell_value(r, 7))
        delivery_time = str(sh.cell_value(r, 9)) if sh.cell_value(r, 9) else '-'
        amount = sh.cell_value(r, 10)
        category = str(sh.cell_value(r, 12))
        rider1 = str(sh.cell_value(r, 16)) if sh.cell_value(r, 16) else ''
        rider2 = str(sh.cell_value(r, 18)) if sh.cell_value(r, 18) else ''
        orders.append(dict(
            id=order_id, prefix=order_id[:3] if order_id else '',
            merchant_id=merchant_id, merchant=merchant,
            type=order_type, status=status,
            order_time=order_time, delivery_time=delivery_time,
            amount=amount, category=category,
            rider1=rider1, rider2=rider2,
        ))

print(f'Total: {len(orders)} orders')
print()

normal = [o for o in orders if o['prefix'] in ('320', '330', '340')]
abnormal = [o for o in orders if o['prefix'] not in ('320', '330', '340')]
cancelled = [o for o in orders if '取消' in o['status']]
no_amount = [o for o in orders if not o['amount']]
merchant_minus1 = [o for o in orders if o['merchant_id'] == -1 or o['merchant_id'] == '-1']
unknown_cat = [o for o in orders if '未知' in o['category']]
single_rider = [o for o in orders if o['rider1'] and not o['rider2']]

print(f'正常订单(320/330/340): {len(normal)}')
print(f'异常订单号(178等):   {len(abnormal)}')
print(f'已取消:              {len(cancelled)}')
print(f'无实付金额:          {len(no_amount)}')
print(f'商家ID=-1:           {len(merchant_minus1)}')
print(f'未知品类:            {len(unknown_cat)}')
print(f'仅1个骑手(非接力):  {len(single_rider)}')
print()

print('=== 异常订单 ===')
for o in abnormal:
    print(f'{o["id"]} | {o["type"]} | {o["status"]} | {o["order_time"]} -> {o["delivery_time"]} | {o["merchant"]} | rider:{o["rider1"]}')

print()
print('=== 正常订单 ===')
for o in normal:
    amt = f'¥{o["amount"]}' if o['amount'] else '无'
    print(f'{o["id"]} | {o["type"]} | {o["status"]} | {o["order_time"]} | {amt} | {o["category"]} | {o["merchant"][:30]} | {o["rider1"]}+{o["rider2"]}')
