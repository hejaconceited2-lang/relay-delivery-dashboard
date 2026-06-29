# -*- coding: utf-8 -*-
import sys, io, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from collections import defaultdict
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

BASE = r"D:\CC' + '接力送日订单' + r'"
sys.path.insert(0, "scripts")
from parse_payroll import parse_payroll
dl, dh, as_ = parse_payroll(os.path.join(BASE, "接力送真实人力计薪", "接力送计薪表格.xlsx"))

COMPANY = {"和业广场", "万菱广场", "金鹰大厦", "汇德国际"}
CONTRACT = {"万科欧泊", "中大附属第六医院", "中大附三岭南医院"}
SPECIAL = {"绿地星玥", "珠江国际轻纺城"}
NOT_OURS = {"新中国大厦", "新亚洲电子城", "孙逸仙北院", "华林国际C馆", "云升科技园"}
XIAOER = {"金鹰大厦": 250, "汇德国际": 350.5}
print("Script regenerated")
