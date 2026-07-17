# -*- coding: utf-8 -*-
"""
接力送 · 盈利诊断报告 PDF 生成器
数据源: _summary_cache.json (由 build_dashboard.py 生成)
用法: python build_report.py           # 全周期
      python build_report.py 2026-06-07 2026-07-09   # 指定区间
      python build_report.py 2026-06-07 2026-07-09 --no-comp  # 去除餐赔
输出: 接力送盈利诊断报告.pdf
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from collections import defaultdict
from datetime import datetime
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.dirname(os.path.abspath(__file__))
FONT = 'C:/Windows/Fonts/simhei.ttf'
CACHE = os.path.join(BASE, '_summary_cache.json')

# ══════════════════════════════════════════════════════
# 站点分成分类 (2026-07-10 用户确认版)
# ══════════════════════════════════════════════════════
COMPANY  = {'和业广场', '万菱广场', '金鹰大厦', '汇德国际', '华林国际C馆', '交易广场', '高科大厦（新）'}      # 直营 100%
CONTRACT = {'万科欧泊', '中大附属第六医院', '中大附三岭南医院', '中大附属第三医院', '上城敏捷'}          # 承包 50%
SPECIAL  = {'绿地星玥', '珠江国际轻纺城'}                                                    # 抽成 0.5元/单
NOT_OURS = {'新中国大厦', '新亚洲电子城', '孙逸仙北院', '云升科技园'}                          # 剔除

DRAW_RATE = 0.5          # 抽成价 元/单
CONTRACT_SHARE = 0.5     # 承包公司分成比例


def classify(name):
    if name in COMPANY:  return 'company'
    if name in CONTRACT: return 'contract'
    if name in SPECIAL:  return 'special'
    return 'exclude'


def load_data(start=None, end=None, no_comp=False):
    """读缓存, 按区间聚合每站数据"""
    cache = json.load(open(CACHE, encoding='utf-8'))
    dates = sorted(cache.keys())
    if start: dates = [d for d in dates if d >= start]
    if end:   dates = [d for d in dates if d <= end]

    # 逐站聚合
    st = defaultdict(lambda: {
        '天数': 0, '订单量': 0, '已完成': 0, '取消赔偿': 0.0,
        '结算收入': 0.0, '人力成本': 0.0, '补贴': 0.0, '净利': 0.0,
        '低单量天': 0, '无补贴天': 0, '赔偿爆炸次': 0, '人力缺失天': 0,
    })
    daily = []  # 每日每站明细(诊断用)

    def num(v):  # None-safe 取数
        return v if isinstance(v, (int, float)) else 0.0

    for d in dates:
        day = cache[d]
        for s in day.get('station_profits', []):
            n = s['站点']
            cls = classify(n)
            if cls == 'exclude':
                continue
            a = st[n]
            a['天数'] += 1
            a['订单量'] += num(s['订单量'])
            a['已完成'] += num(s['已完成'])
            a['取消赔偿'] += num(s['取消赔偿'])
            a['结算收入'] += num(s['结算收入'])
            a['补贴'] += num(s['补贴'])
            # 人力: 抽成站不担人力(记0), 其余站None视为未确认并计数
            if cls != 'special' and s.get('人力成本') is None:
                a['人力缺失天'] += 1
            a['人力成本'] += num(s.get('人力成本'))
            # 诊断计数
            if num(s['订单量']) < 50: a['低单量天'] += 1
            if num(s['补贴']) == 0 and num(s['系统登记']) > 1: a['无补贴天'] += 1
            if num(s['取消赔偿']) > 100:
                a['赔偿爆炸次'] += 1
            daily.append({'日期': d, **{k: (num(v) if k in ('订单量','已完成','取消赔偿','结算收入','人力成本','补贴','净利','人均单量','系统登记') else v) for k, v in s.items()}})

    # 计算每站利润 + 公司分成 (no_comp=True 时取消赔偿计为0)
    def comp(a):
        return 0 if no_comp else a['取消赔偿']

    rows = []
    for n, a in st.items():
        cls = classify(n)
        if cls == 'special':
            # 抽成: 公司只拿 0.5元/完成单, 不担人力/赔偿
            station_profit = a['结算收入'] + a['补贴'] - a['人力成本'] - comp(a)
            company_share = a['已完成'] * DRAW_RATE
        elif cls == 'contract':
            station_profit = a['结算收入'] + a['补贴'] - a['人力成本'] - comp(a)
            company_share = station_profit * CONTRACT_SHARE
        else:  # company 直营
            station_profit = a['结算收入'] + a['补贴'] - a['人力成本'] - comp(a)
            company_share = station_profit
        rows.append({
            '站点': n, '类别': cls, '天数': a['天数'],
            '日均单': round(a['订单量'] / a['天数']) if a['天数'] else 0,
            '总单量': a['订单量'], '已完成': a['已完成'],
            '结算收入': a['结算收入'], '补贴': a['补贴'],
            '美团收入': a['结算收入'] + a['补贴'],
            '人力成本': a['人力成本'], '取消赔偿': a['取消赔偿'],
            '站点利润': station_profit, '公司分成': company_share,
            '低单量天': a['低单量天'], '无补贴天': a['无补贴天'],
            '赔偿爆炸次': a['赔偿爆炸次'],
        })
    rows.sort(key=lambda r: -r['公司分成'])
    return dates, rows, daily


def build_trend_chart(dates, cache, out, no_comp=False):
    """公司日分成走势图"""
    def num(v):
        return v if isinstance(v, (int, float)) else 0.0
    xs, ys = [], []
    for d in dates:
        day = cache[d]
        prof = 0.0
        for s in day.get('station_profits', []):
            n = s['站点']
            cls = classify(n)
            if cls == 'exclude': continue
            comp = 0 if no_comp else num(s['取消赔偿'])
            sp = num(s['结算收入']) + num(s['补贴']) - num(s.get('人力成本')) - comp
            if cls == 'special':
                prof += num(s['已完成']) * DRAW_RATE
            elif cls == 'contract':
                prof += sp * CONTRACT_SHARE
            else:
                prof += sp
        xs.append(d[5:]); ys.append(prof)
    fp = font_manager.FontProperties(fname=FONT)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    colors = ['#ef4444' if y < 0 else '#22c55e' for y in ys]
    ax.bar(xs, ys, color=colors)
    ax.axhline(0, color='#334155', lw=0.8)
    ax.set_title('公司日分成走势', fontproperties=fp, fontsize=13)
    ax.tick_params(axis='x', rotation=90, labelsize=6)
    ax.grid(axis='y', ls=':', alpha=0.4)
    plt.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close()
    return xs, ys


class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font('hei', '', FONT, uni=True)

    def cn(self, size, style=''):
        self.set_font('hei', '', size)


def money(v):
    return f'{v:+,.0f}' if v else '0'


def main():
    args = [a for a in sys.argv[1:]]
    no_comp = '--no-comp' in args
    date_args = [a for a in args if a != '--no-comp']
    start = date_args[0] if len(date_args) > 0 else None
    end = date_args[1] if len(date_args) > 1 else None

    cache = json.load(open(CACHE, encoding='utf-8'))
    dates, rows, daily = load_data(start, end, no_comp=no_comp)
    chart = os.path.join(BASE, '_trend_report.png')
    xs, ys = build_trend_chart(dates, cache, chart, no_comp=no_comp)

    total_orders = sum(r['总单量'] for r in rows)
    total_share = sum(r['公司分成'] for r in rows)
    total_meituan = sum(r['美团收入'] for r in rows)
    profit_days = sum(1 for y in ys if y > 0)
    avg_share = total_share / len(dates) if dates else 0
    retention = total_share / total_meituan * 100 if total_meituan > 0 else 0
    comp_note = '（去除餐赔）' if no_comp else ''
    span_label = f'{dates[0]} - {dates[-1]}  |  共{len(dates)}天  |  {len(rows)}个站点'

    pdf = PDF()
    pdf.set_auto_page_break(True, 15)

    # ═══ 第1页 封面 ═══
    pdf.add_page()
    pdf.cn(26); pdf.ln(30)
    pdf.cell(0, 16, '接力送', align='C'); pdf.ln(16)
    pdf.cn(20); pdf.cell(0, 12, f'盈利诊断报告{comp_note}', align='C'); pdf.ln(20)
    pdf.cn(11); pdf.cell(0, 8, span_label, align='C'); pdf.ln(20)
    pdf.cn(13)
    pdf.cell(0, 10, f'公司总分成  {money(total_share)} 元', align='C'); pdf.ln(10)
    pdf.cell(0, 10, f'日均分成  {money(avg_share)} 元', align='C'); pdf.ln(10)
    pdf.cell(0, 10, f'美团总收入  {total_meituan:,.0f} 元  (留存率 {retention:.1f}%)', align='C'); pdf.ln(10)
    pdf.cell(0, 10, f'总单量  {total_orders:,} 单', align='C'); pdf.ln(10)
    pdf.cell(0, 10, f'盈利天数  {profit_days} / {len(dates)} 天', align='C')

    # ═══ 第2页 走势 + 总览 ═══
    pdf.add_page()
    pdf.cn(14); pdf.cell(0, 10, '一、公司日分成走势'); pdf.ln(12)
    pdf.image(chart, x=12, w=186); pdf.ln(4)
    pdf.cn(14); pdf.cell(0, 10, '二、站点盈利总览'); pdf.ln(10)
    _table(pdf, rows, mode='overview')

    # ═══ 第3/4/5页 分类明细 ═══
    for cls, title in [('company', '直营站点（100%归属公司）'),
                       ('contract', '承包站点（50%归属公司）'),
                       ('special', '抽成站点（每单0.5元）')]:
        pdf.add_page()
        pdf.cn(14); pdf.cell(0, 10, title); pdf.ln(12)
        _table(pdf, [r for r in rows if r['类别'] == cls], mode=cls)

    # ═══ 第6页 亏损诊断 ═══
    pdf.add_page()
    pdf.cn(14); pdf.cell(0, 10, '三、亏损诊断'); pdf.ln(12)
    _diagnosis(pdf, rows, daily, no_comp=no_comp)

    # ═══ 第7页 结论 ═══
    pdf.add_page()
    pdf.cn(14); pdf.cell(0, 10, '四、结论与建议'); pdf.ln(12)
    _conclusion(pdf, rows, no_comp=no_comp)

    # 输出文件名
    if no_comp:
        if start and end:
            out = os.path.join(BASE, f'接力送盈利诊断报告_{start}_{end}_去除餐赔.pdf')
        elif start:
            out = os.path.join(BASE, f'接力送盈利诊断报告_{start}_至今_去除餐赔.pdf')
        else:
            out = os.path.join(BASE, '接力送盈利诊断报告_去除餐赔.pdf')
    else:
        out = os.path.join(BASE, '接力送盈利诊断报告.pdf')
    pdf.output(out)
    print(f'[OK] 已生成: {out}')
    print(f'  区间: {span_label}')
    print(f'  公司总分成: {money(total_share)}元  日均{money(avg_share)}元  盈利{profit_days}/{len(dates)}天')


def _table(pdf, rows, mode):
    """通用表格"""
    if mode == 'overview':
        heads = ['站点', '天', '日均', '总单', '结算', '补贴', '美团收入', '人力', '赔偿', '分成']
        ws = [30, 8, 13, 16, 18, 16, 20, 18, 16, 20]
    else:
        heads = ['站点', '天', '日均', '总单', '结算', '美团收入', '人力', '赔偿', '站点利润', '公司分成']
        ws = [30, 8, 12, 16, 18, 18, 16, 16, 20, 20]
    pdf.cn(8)
    for h, w in zip(heads, ws):
        pdf.cell(w, 7, h, border=1, align='C')
    pdf.ln()
    subtotal = 0
    for r in rows:
        subtotal += r['公司分成']
        if mode == 'overview':
            cells = [r['站点'], r['天数'], r['日均单'], r['总单量'],
                     f"{r['结算收入']:,.0f}", f"{r['补贴']:,.0f}",
                     f"{r['美团收入']:,.0f}",
                     f"{r['人力成本']:,.0f}", f"{r['取消赔偿']:,.0f}",
                     money(r['公司分成'])]
        else:
            cells = [r['站点'], r['天数'], r['日均单'], r['总单量'],
                     f"{r['结算收入']:,.0f}",
                     f"{r['美团收入']:,.0f}",
                     f"{r['人力成本']:,.0f}",
                     f"{r['取消赔偿']:,.0f}", money(r['站点利润']),
                     money(r['公司分成'])]
        for c, w in zip(cells, ws):
            pdf.cell(w, 6, str(c), border=1, align='C')
        pdf.ln()
    # 小计
    pdf.cn(8)
    pdf.cell(sum(ws[:-1]), 6, '小计', border=1, align='C')
    pdf.cell(ws[-1], 6, money(subtotal), border=1, align='C')
    pdf.ln()


def _diagnosis(pdf, rows, daily, no_comp=False):
    # TOP8 单日亏损
    losses = []
    for d in daily:
        cls = classify(d['站点'])
        comp = 0 if no_comp else d['取消赔偿']
        sp = d['结算收入'] + d['补贴'] - d['人力成本'] - comp
        if cls == 'special':
            share = d['已完成'] * DRAW_RATE
        elif cls == 'contract':
            share = sp * CONTRACT_SHARE
        else:
            share = sp
        if share < 0:
            losses.append({'日期': d['日期'], '站点': d['站点'], '单量': d['订单量'],
                           '登记': d['系统登记'], '人均': d['人均单量'],
                           '达标': d['达标'], '人力': d['人力成本'],
                           '赔偿': d['取消赔偿'], '亏损': share})
    losses.sort(key=lambda x: x['亏损'])

    pdf.cn(11); pdf.cell(0, 8, '单日亏损 TOP 8'); pdf.ln(10)
    heads = ['日期', '站点', '单量', '登记', '人均', '达标', '人力', '赔偿', '亏损']
    ws = [24, 32, 16, 14, 16, 16, 18, 18, 20]
    pdf.cn(8)
    for h, w in zip(heads, ws): pdf.cell(w, 7, h, border=1, align='C')
    pdf.ln()
    for l in losses[:8]:
        cells = [l['日期'][5:], l['站点'], l['单量'], l['登记'],
                 f"{l['人均']:.0f}", '达标' if l['达标'] == 'Y' else '未达',
                 f"{l['人力']:.0f}", f"{l['赔偿']:.0f}", f"{l['亏损']:.0f}"]
        for c, w in zip(cells, ws): pdf.cell(w, 6, str(c), border=1, align='C')
        pdf.ln()
    pdf.ln(4)

    # 三大根因
    total_comp = sum(r['取消赔偿'] for r in rows)
    comp_times = sum(r['赔偿爆炸次'] for r in rows)
    no_sub_days = sum(r['无补贴天'] for r in rows)
    low_days = sum(r['低单量天'] for r in rows)
    pdf.cn(11); pdf.cell(0, 8, '三大亏损根因'); pdf.ln(9)
    pdf.cn(9)
    if no_comp:
        txt = [
            f'一、人均不达标失去补贴：{no_sub_days}个站天人均<20单，(登记-1)x80补贴归零，人力不变直接扩大亏损。',
            f'二、结构性低单量：{low_days}个站天日单量<50，结算收入无法覆盖固定人力。建议缩减人员或合并站点。',
            f'三、餐赔参考：合计赔偿 {total_comp:,.0f}元，{comp_times}次单日超100元（已从本次利润计算中剔除）。属运营管控问题，可通过加强管理减少。',
        ]
    else:
        txt = [
            f'一、取消赔偿爆炸：{comp_times}次单日超100元，合计赔偿 {total_comp:,.0f}元。属运营管控问题，可通过加强管理减少。',
            f'二、人均不达标失去补贴：{no_sub_days}个站天人均<20单，(登记-1)x80补贴归零，人力不变直接扩大亏损。',
            f'三、结构性低单量：{low_days}个站天日单量<50，结算收入无法覆盖固定人力。建议缩减人员或合并站点。',
        ]
    for t in txt:
        pdf.multi_cell(0, 6, t); pdf.ln(1)


def _conclusion(pdf, rows, no_comp=False):
    pdf.cn(9)
    # 找最大利润支柱
    pillar = max(rows, key=lambda r: r['公司分成'])
    losers = [r for r in rows if r['公司分成'] < 0]
    total = sum(r['公司分成'] for r in rows)
    comp_note = '（餐赔已从利润中剔除）' if no_comp else ''
    txt = [
        f'利润支柱：{pillar["站点"]}，公司分成 {money(pillar["公司分成"])}元' +
        (f'，占公司总分成的{pillar["公司分成"]/total*100:.0f}%。' if total > 0 else '。') +
        f'是当前最关键的盈利来源，需密切关注其单量稳定性。{comp_note}',
        '',
        f'亏损站点：共{len(losers)}个站点公司分成为负' +
        (f'（{", ".join(r["站点"] for r in losers)}）' if losers else '') +
        '。主因是低单量+高人力配置，建议按单量重新核定人员编制。',
        '',
        '核心结论：盈利高度依赖头部站点与平台补贴。补贴窗口期内应聚焦高单量站点，' +
        '压缩低效站点人力，将赔偿控制作为日常管控重点。',
    ]
    for t in txt:
        if t: pdf.multi_cell(0, 7, t)
        else: pdf.ln(3)


if __name__ == '__main__':
    main()
