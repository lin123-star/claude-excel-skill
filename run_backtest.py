# 回测运行脚本
"""
run_backtest.py
入口脚本：支持单股和沪深300批量回测

用法：
  python run_backtest.py --stock 000001 --start 2020-01-01 --end 2024-12-31
  python run_backtest.py --batch --start 2020-01-01 --end 2024-12-31 --top 20
"""

import argparse
import json
import logging
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from data_fetcher import get_index_components, fetch_daily_data, fetch_batch
from factors.technical import add_signals
from engine import BacktestEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_single(stock_code: str, start_date: str, end_date: str, engine: BacktestEngine) -> dict | None:
    """回测单只股票，返回结果字典"""
    df = fetch_daily_data(stock_code, start_date, end_date)
    if df.empty:
        return None

    df = add_signals(df)
    df = df.dropna(subset=["ma30"])  # 去掉MA30未形成的早期数据

    result = engine.run(df)
    result["stock_code"] = stock_code
    result["start_date"] = start_date
    result["end_date"] = end_date
    return result


def run_batch(start_date: str, end_date: str, top_n: int = 20, index_code: str = "000300"):
    """批量回测指数成分股，输出汇总排名"""
    codes = get_index_components(index_code)
    if not codes:
        logger.error(f"无法获取指数{index_code}成分股列表")
        return

    engine = BacktestEngine()
    summary = []

    for i, code in enumerate(codes, 1):
        logger.info(f"回测进度 {i}/{len(codes)}: {code}")
        result = run_single(code, start_date, end_date, engine)
        if result and result.get("metrics"):
            m = result["metrics"]
            summary.append({
                "stock_code": code,
                "total_return": m.get("total_return", 0),
                "annual_return": m.get("annual_return", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "sharpe_ratio": m.get("sharpe_ratio", 0),
                "trade_count": len(result.get("trades", [])),
            })

    if not summary:
        logger.error("所有股票回测均失败")
        return

    summary_df = pd.DataFrame(summary).sort_values("sharpe_ratio", ascending=False)

    # 保存完整汇总CSV
    csv_path = OUTPUT_DIR / f"batch_summary_{start_date}_{end_date}.csv"
    summary_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"汇总结果已保存: {csv_path}")

    # 输出Top N
    print(f"\n{'='*60}")
    print(f"沪深300回测汇总 Top {top_n}（按夏普比率排序）")
    print(f"回测区间：{start_date} ~ {end_date}")
    print(f"{'='*60}")
    print(summary_df.head(top_n).to_string(index=False))

    # 保存Top N的详细结果
    top_codes = summary_df.head(top_n)["stock_code"].tolist()
    top_results = []
    for code in top_codes:
        result = run_single(code, start_date, end_date, engine)
        if result and result.get("metrics"):
            top_results.append(result)

    json_path = OUTPUT_DIR / f"top{top_n}_detail_{start_date}_{end_date}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(top_results, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Top {top_n} 详细结果已保存: {json_path}")

    return summary_df


def main():
    parser = argparse.ArgumentParser(description="A股量化回测工具")
    parser.add_argument("--stock", type=str, help="单只股票代码，如 000001")
    parser.add_argument("--batch", action="store_true", help="批量回测指数成分股")
    parser.add_argument("--start", type=str, default="2020-01-01", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", type=str, default="2024-12-31", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--top", type=int, default=20, help="批量模式：显示Top N结果")
    parser.add_argument("--index", type=str, default="000300", help="指数代码，默认000300")
    args = parser.parse_args()

    if args.stock:
        engine = BacktestEngine()
        result = run_single(args.stock, args.start, args.end, engine)
        if result:
            out_path = OUTPUT_DIR / f"{args.stock}_result.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n回测完成：{args.stock}")
            print(f"总收益率: {result['metrics']['total_return']:.2%}")
            print(f"年化收益: {result['metrics']['annual_return']:.2%}")
            print(f"最大回撤: {result['metrics']['max_drawdown']:.2%}")
            print(f"夏普比率: {result['metrics']['sharpe_ratio']:.2f}")
            print(f"交易次数: {len(result['trades'])}")
            print(f"详细结果: {out_path}")

    elif args.batch:
        run_batch(args.start, args.end, args.top, args.index)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()