from data_fetcher import fetch_daily_data
from factors.technical import add_signals

df = fetch_daily_data("002460", "2020-01-01", "2024-12-31")
df = add_signals(df)
df = df.dropna(subset=["ma30"])

# 看各条件单独触发次数
print("总交易日数:", len(df))
# debug.py 里这行也要改
print("跌破MA30*80%天数:", (df["close"] <= df["ma30"] * 0.80).sum())
print("跌幅≥5%天数:", (df["daily_return"] <= -0.05).sum())
print("量比≥2倍天数:", (df["vol_ratio"] >= 2.0).sum())
print("三条件同时满足:", ((df["below_ma30"]) & (df["daily_return"] <= -0.05) & (df["vol_ratio"] >= 2.0)).sum())
print("entry_signal触发次数:", df["entry_signal"].sum())