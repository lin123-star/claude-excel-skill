# 技术因子模块
"""
factors/technical.py
技术因子计算：MA30、跌幅、量比
所有信号均 shift(1) 防前视偏差
"""

import pandas as pd


def add_signals(
    df: pd.DataFrame,
    ma_window: int = 30,
    drop_threshold: float = 0.05,
    vol_ratio_threshold: float = 2.0,
    vol_lookback: int = 5,
) -> pd.DataFrame:
    """
    计算策略所需全部技术信号，返回新增列的DataFrame。

    新增列说明：
    - ma30           : 30日收盘价均线
    - daily_return   : 当日涨跌幅
    - vol_ma5        : 前5日成交量均值
    - vol_ratio      : 当日量 / vol_ma5
    - below_ma30     : 收盘价是否跌破MA30（bool）
    - entry_signal   : 建仓信号（已 shift(1)，1=触发，0=未触发）
    - above_ma30     : 收盘价是否站上MA30（bool）
    - exit_signal    : 清仓信号（已 shift(1)，1=触发，0=未触发）
    """
    df = df.copy()

    # ── 基础指标 ──────────────────────────────────────────
    df["ma30"] = df["close"].rolling(ma_window, min_periods=ma_window).mean()
    df["daily_return"] = df["close"].pct_change()

    # 前5日均量（不含当日，用 shift(1) 后再rolling避免前视）
    df["vol_ma5"] = (
        df["volume"].shift(1).rolling(vol_lookback, min_periods=vol_lookback).mean()
    )
    df["vol_ratio"] = df["volume"] / df["vol_ma5"]

    # ── 原始条件（基于当日数据，尚未防前视）────────────────
    below_ma30_raw = df["close"] <= df["ma30"] * 0.80
    big_drop_raw = df["daily_return"] <= -drop_threshold
    big_volume_raw = df["vol_ratio"] >= vol_ratio_threshold

    # ── shift(1)：信号在下一个交易日才能执行 ───────────────
    # 即：今天收盘后看到信号，明天开盘买入（以收盘价模拟）
    df["below_ma30"] = below_ma30_raw
    df["entry_signal"] = below_ma30_raw.shift(1).fillna(False).astype(int)
    
    # 清仓由持仓天数控制（>= 125日自动清仓），不再依赖价格反弹至MA30
    df["exit_signal"] = 0  # 保留列以兼容引擎，但不再使用价格信号

    return df