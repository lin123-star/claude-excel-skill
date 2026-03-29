# 回测引擎模块
"""
engine.py
回测核心引擎：模拟分批建仓/加仓/清仓，计算净值和绩效指标
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class Position:
    """持仓状态"""
    shares: float = 0.0          # 持股数量
    cost_basis: float = 0.0      # 平均成本价
    entry_price: float = 0.0     # 首次建仓价（用于计算加仓触发点）
    added: bool = False          # 是否已加仓
    hold_days: int = 0            # 持仓天数


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission: float = 0.0003,   # 万三手续费
        slippage: float = 0.001,      # 0.1% 滑点
        position_first: float = 0.20, # 首次建仓仓位
        position_add: float = 0.40,   # 加仓仓位
        add_trigger_drop: float = 0.20,  # 加仓触发：建仓后再跌X%
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_first = position_first
        self.position_add = position_add
        self.add_trigger_drop = add_trigger_drop

    def run(self, df: pd.DataFrame) -> dict:
        """
        执行单只股票回测。
        df 必须包含：date, close, volume, entry_signal, exit_signal
        返回结果字典。
        """
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        df["prev_close"] = df["close"].shift(1)
        df["entry_signal"] = df["entry_signal"].fillna(0).astype(int)
        df["exit_signal"] = df["exit_signal"].fillna(0).astype(int)
        if df.empty:
            return {"metrics": {}, "daily_portfolio": [], "trades": []}

        cash = self.initial_capital
        pos = Position()
        trades = []
        daily_records = []

        for _, row in df.iterrows():
            date = row["date"]
            price = row["close"]
            if price <= 0:
                continue
            entry = row["entry_signal"]
            exit_ = row["exit_signal"]

            # 涨跌停判断：成交量为0视为停牌，跳过交易
            if row.get("volume", 1) == 0:
                portfolio_value = cash + pos.shares * price
                daily_records.append({"date": date, "portfolio_value": portfolio_value, "signal": 0})
                continue

            action_taken = 0

            # ── 清仓逻辑（优先于建仓）───────────────────────
            # 当达到持仓天数上限（125日）或遇到退出信号时清仓
            if pos.shares > 0 and (exit_ == 1 or pos.hold_days >= 125):
                sell_price = price * (1 - self.slippage)
                proceeds = pos.shares * sell_price * (1 - self.commission)
                trades.append({
                    "date": date, "action": "sell",
                    "price": round(sell_price, 4),
                    "shares": round(pos.shares, 2),
                    "proceeds": round(proceeds, 2),
                    "pnl": round(proceeds - pos.shares * pos.cost_basis, 2),
                })
                cash += proceeds
                pos = Position()  # 清空持仓
                action_taken = -1

            # ── 建仓逻辑 ────────────────────────────────────
            elif entry == 1 and pos.shares == 0:
                buy_price = row["prev_close"] * (1 + self.slippage)
                # 价格有效性检查：避免除以0或异常价格
                if buy_price > 0 and (buy_price * (1 + self.commission)) > 0:
                    invest_amount = self.initial_capital * self.position_first
                    invest_amount = min(invest_amount, cash)  # 不超过可用现金
                    shares_bought = invest_amount / (buy_price * (1 + self.commission))
                    cost = shares_bought * buy_price * (1 + self.commission)
                else:
                    shares_bought = 0
                    cost = 0

                if shares_bought > 0:
                    cash -= cost
                    pos.shares = shares_bought
                    pos.cost_basis = buy_price
                    pos.entry_price = buy_price
                    pos.added = False
                    trades.append({
                        "date": date, "action": "buy_first",
                        "price": round(buy_price, 4),
                        "shares": round(shares_bought, 2),
                        "cost": round(cost, 2),
                    })
                    action_taken = 1

            # ── 加仓逻辑 ────────────────────────────────────
            elif pos.shares > 0 and not pos.added:
                if pos.entry_price > 0:
                    drop_from_entry = (price - pos.entry_price) / pos.entry_price
                else:
                    drop_from_entry = 0
                
                if drop_from_entry <= -self.add_trigger_drop:
                    buy_price = price * (1 + self.slippage)
                    # 价格有效性检查：避免除以0或异常价格
                    if buy_price > 0 and (buy_price * (1 + self.commission)) > 0:
                        invest_amount = self.initial_capital * self.position_add
                        invest_amount = min(invest_amount, cash)
                        shares_bought = invest_amount / (buy_price * (1 + self.commission))
                        cost = shares_bought * buy_price * (1 + self.commission)
                    else:
                        shares_bought = 0
                        cost = 0

                    if shares_bought > 0:
                        # 更新平均成本
                        total_shares = pos.shares + shares_bought
                        pos.cost_basis = (pos.shares * pos.cost_basis + shares_bought * buy_price) / total_shares
                        pos.shares = total_shares
                        pos.added = True
                        cash -= cost
                        trades.append({
                            "date": date, "action": "buy_add",
                            "price": round(buy_price, 4),
                            "shares": round(shares_bought, 2),
                            "cost": round(cost, 2),
                        })
                        action_taken = 2

            portfolio_value = cash + pos.shares * price
            daily_records.append({
                "date": date,
                "portfolio_value": portfolio_value,
                "signal": action_taken,
            })

            # 持仓天数更新：当持仓时递增，平仓时重置
            if pos.shares > 0:
                pos.hold_days += 1
            else:
                pos.hold_days = 0

        # ── 计算绩效 ─────────────────────────────────────────
        daily_df = pd.DataFrame(daily_records)
        metrics = self._calc_metrics(daily_df["portfolio_value"])

        return {
            "metrics": metrics,
            "daily_portfolio": daily_records,
            "trades": trades,
        }

    def _calc_metrics(self, portfolio_series: pd.Series) -> dict:
        if len(portfolio_series) < 2:
            return {}

        values = portfolio_series.values
        returns = pd.Series(values).pct_change().dropna()

        total_return = (values[-1] - self.initial_capital) / self.initial_capital
        n_days = len(values)
        annual_return = (1 + total_return) ** (252 / n_days) - 1

        # 最大回撤
        cummax = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cummax) / cummax
        max_drawdown = drawdown.min()

        # 夏普比率（无风险利率3%年化，折日）
        rf_daily = 0.03 / 252
        excess_returns = returns - rf_daily
        sharpe = (excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0

        return {
            "total_return": round(float(total_return), 4),
            "annual_return": round(float(annual_return), 4),
            "max_drawdown": round(float(max_drawdown), 4),
            "sharpe_ratio": round(float(sharpe), 4),
        }