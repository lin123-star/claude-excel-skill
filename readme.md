## 🧩 项目整体流程（从数据到策略到回测）

1. run_backtest.py 是入口
   - 接受参数：`--stock`, `--start`, `--end`, `--batch`
   - 单股模式调用 `run_single`; 批量模式调用 `run_batch`
   - 输出 JSON、CSV、Top N 等结果

2. 数据模块：data_fetcher.py
   - 从 AKShare 拉取日线历史（ `ak.stock_zh_a_hist` ）
   - 支持本地缓存（cache）
   - 缓存格式 parquet（读/写需 `pyarrow` / `fastparquet`）

3. 因子信号：technical.py
   - 计算均线 `ma30`、日涨跌、量比
   - 生成建仓 `entry_signal`（工作日+1为了防前视）
   - 现在已强制空出 `exit_signal`（0），清仓由持仓天数控制

4. 回测引擎：engine.py
   - `BacktestEngine.run(df)` 逐日循环
   - 日期、收盘、信号、成交量、仓位都计算
   - 交易逻辑：
     - 先清仓（`exit_signal==1` or `pos.hold_days >=125`）
     - 再建仓（`entry_signal==1` + 空仓）
     - 加仓（跌幅超过 `add_trigger_drop`，且未加过）
   - 成本/滑点/手续费模拟
   - 记录 `daily_portfolio`、`trades`

5. 绩效计算（`engine._calc_metrics`）
   - 总收益/年化收益
   - 最大回撤
   - 夏普率（无风险 3%）

---

## ⚙️ 核心技术点

- 数据获取：AKShare + 本地缓存
- 信号策略：技术指标（30日均线打底、量价过滤）
- 回测流程：逐日回测、模拟买卖、记录买卖行为
- 风险控制：
  - 固定 `slippage`（0.1%）
  - 交易手续费 `commission`（万3）
  - 持仓天数控制（≥125 退场）
- 模块化：数据/因子/引擎分离，便于扩展（加新因子、新策略）

---

## 💡 你目前的关键行为（已完成）

- `data_fetcher` 可正常拉数据（需安装依赖 `pyarrow`/`fastparquet`）
- `technical` 只保留 `entry_signal`，`exit_signal` 由引擎 `冗余 0`
- `engine` 清仓条件为持仓日 >= 125（且兼容 `exit_signal`）
- `run_backtest` 负责传参、存储结果、汇总分析

---

## ✅ 运行复现顺序

1. 激活环境
   - Activate.ps1
2. 安装依赖
   - `pip install -r requirements.txt`
   - `pip install pyarrow`（或 fastparquet）
3. 运行回测
   - `python run_backtest.py --stock 000001 --start 2020-01-01 --end 2024-12-31`

---

## 🔍 你现在的策略逻辑（结合代码）

- 选股：`收盘价 <= MA30*0.8` 触发持仓（前一天信号）
- 退出：持仓天数满 125 日（不考虑价格站上 MA30）
- 加仓：首仓后股价跌 20% 触发
- 绩效统计按净值序列算

---

## 🛠️ 如果要继续优化

- 加 `stop-loss` / `take-profit`
- 将 `exit_signal` 改为策略判断（可混合持仓天+技术退出）
- 改 cache 为 CSV 可兼容无 parquet 的环境
- `run_batch` 增加并发异步提升效率
- 画图、回测报告更可视（`matplotlib`, `plotly`）
