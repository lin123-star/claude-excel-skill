# 数据获取模块
"""
data_fetcher.py
AKShare数据获取模块，带本地parquet缓存
"""

import os
import logging
import pandas as pd
import akshare as ak
from pathlib import Path

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_index_components(index_code: str = "000300") -> list[str]:
    """
    返回指数成分股列表
    常用指数代码：
      000300 = 沪深300
      000852 = 中证1000
      000905 = 中证500
      000016 = 上证50
    """
    try:
        df = ak.index_stock_cons_weight_csindex(symbol=index_code)
        codes = df["成分券代码"].astype(str).str.zfill(6).tolist()
        logger.info(f"获取指数{index_code}成分股 {len(codes)} 只")
        return codes
    except Exception as e:
        logger.error(f"获取指数{index_code}成分股失败: {e}")
        return []


def fetch_daily_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    拉取单只股票日线数据，带本地缓存。
    返回列：date, open, high, low, close, volume
    """
    cache_file = CACHE_DIR / f"{stock_code}_{start_date}_{end_date}_noadj.parquet"

    if cache_file.exists():
        df = pd.read_parquet(cache_file)
        logger.debug(f"{stock_code} 命中缓存")
        return df

    try:
        raw = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="",  # 不复权
        )
        if raw is None or raw.empty:
            logger.warning(f"{stock_code} 无数据返回")
            return pd.DataFrame()

        df = raw.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        })[["date", "open", "high", "low", "close", "volume"]]

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        df.to_parquet(cache_file, index=False)
        logger.info(f"{stock_code} 数据拉取成功，{len(df)} 条记录")
        return df

    except Exception as e:
        logger.error(f"{stock_code} 数据拉取失败: {e}")
        return pd.DataFrame()


def fetch_batch(
    stock_codes: list[str], start_date: str, end_date: str
) -> dict[str, pd.DataFrame]:
    """批量拉取，返回 {stock_code: DataFrame}，失败的跳过"""
    result = {}
    total = len(stock_codes)
    for i, code in enumerate(stock_codes, 1):
        logger.info(f"进度 {i}/{total}: {code}")
        df = fetch_daily_data(code, start_date, end_date)
        if not df.empty:
            result[code] = df
    logger.info(f"批量拉取完成，成功 {len(result)}/{total} 只")
    return result