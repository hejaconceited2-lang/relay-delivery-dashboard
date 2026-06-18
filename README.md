# 接力送 · 日订单运营看板

> 分段履约站点每日订单数据看板，自动生成 Plotly 交互式 HTML
> 线上地址：https://hejaconceited2-lang.github.io/relay-delivery-dashboard/

## 目录结构

```
relay-delivery-dashboard/
├── index.html              # 总主页（自动生成，汇总所有日期）
├── MMDD.html               # 每日看板（如 0618.html）
├── build_dashboard.py      # 统一构建脚本 ★
├── README.md
├── .gitignore              # 排除 *.xls *.xlsx
│
├── YY-MM-DD/               # 日期数据目录（如 26-06-18）
│   ├── [新]校园订单详情_*.xls   # 原始数据（gitignored）
│   ├── operations_dashboard.html  # 看板输出
│   ├── index.html               # 看板副本
│   ├── check_update.py          # 数据快查脚本
│   ├── pickup_orders.py         # 配送中订单报告
│   └── ...                      # 其他分析脚本
│
└── YY-MM-DD/               # 更多日期...
```

## 新增日期

每天数据更新后，按以下步骤操作：

1. **导出数据**：从美团后台导出「校园订单详情」Excel，筛选含「分段履约」的站点
2. **放入目录**：将 xls 文件放入对应日期目录 `YY-MM-DD/`（如 `26-06-19/`）
3. **运行构建**：
   ```bash
   python build_dashboard.py 2026-06-19
   ```
4. **推送上线**：
   ```bash
   git add . && git commit -m "新增 06-19 看板" && git push origin main
   ```

## 统一构建命令

| 命令 | 作用 |
|------|------|
| `python build_dashboard.py 2026-06-18` | 构建指定日期看板 |
| `python build_dashboard.py --all` | 重建所有日期看板 |
| `python build_dashboard.py --update-index` | 仅更新总主页 |

构建单个日期时会自动同步更新根目录 `MMDD.html` 和总主页 `index.html`。

## 站点编制配置

编制在 `build_dashboard.py` 顶部的 `KNOWN_STAFF` 字典中集中维护。如有日期特定的编制差异（如某站在某天人数不同），在 `STAFF_OVERRIDES` 中按日期覆盖。

新增站点时，只需在 `KNOWN_STAFF` 中添加一行即可。

## 数据规范

- 原始 xls 文件不纳入版本控制（已在 `.gitignore` 中排除）
- 生成的所有 HTML 文件纳入版本控制（用于 GitHub Pages 部署）
- Python 分析脚本按日期目录存放，共享逻辑集中在 `build_dashboard.py`

## 技术栈

- Python 3.12+ / pandas / plotly
- GitHub Pages 静态托管
- 暗色玻璃质感 UI（Plotly dark theme + CSS custom properties）
