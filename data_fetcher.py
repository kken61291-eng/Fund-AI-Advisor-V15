import akshare as ak
import pandas as pd
import time
import random
import numpy as np
from datetime import datetime, time as dt_time
from utils import logger, retry, get_beijing_time

try:
    import yfinance as yf
except ImportError:
    yf = None

class DataFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def _is_trading_time(self):
        now = get_beijing_time()
        if now.weekday() >= 5: return False
        current_time = now.time()
        start = dt_time(9, 30)
        end = dt_time(15, 0)
        return start <= current_time <= end

    @retry(retries=2, delay=2)
    def get_market_volatility(self, window=20):
        """[V15] 获取市场波动率"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000300")
            if df.empty: return 0.015
            df['close'] = pd.to_numeric(df['close'])
            df['pct_change'] = df['close'].pct_change()
            volatility = df['pct_change'].tail(window).std()
            logger.info(f"🌊 [市场环境] 沪深300 近{window}日波动率: {volatility:.2%}")
            return volatility
        except Exception:
            return 0.015

    def _fetch_realtime_candle(self, code):
        """V14.28 实时快照"""
        try:
            df_spot = ak.stock_zh_a_spot_em()
            target = df_spot[df_spot['代码'] == code]
            if target.empty: return None
            
            row = target.iloc[0]
            current_close = float(row['最新价'])
            if current_close <= 0: return None

            candle = pd.Series({
                'close': current_close,
                'high': float(row['最高']),
                'low': float(row['最低']),
                'open': float(row['今开']),
                'volume': float(row['成交量']) if '成交量' in row else 0.0,
                'date': get_beijing_time().replace(hour=0, minute=0, second=0, microsecond=0)
            })
            return candle
        except Exception:
            return None

    @retry(retries=2, delay=3)
    def get_fund_history(self, code):
        """V14 完整兜底逻辑: 东财 -> 新浪 -> Yahoo"""
        time.sleep(random.uniform(1.0, 2.0))
        df_hist = None

        # 1. 东财
        try:
            df = ak.fund_etf_hist_em(symbol=code, period="daily", start_date="20200101", end_date="20500101")
            if not df.empty:
                df = df.rename(columns={"日期": "date", "收盘": "close", "最高": "high", "最低": "low", "开盘": "open", "成交量": "volume"})
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df_hist = df
        except Exception as e:
            logger.warning(f"东财源微瑕 {code}: {str(e)[:50]}")

        # 2. 新浪兜底
        if df_hist is None or df_hist.empty:
            try:
                symbol = f"sh{code}" if code.startswith('5') or code.startswith('6') else f"sz{code}"
                df = ak.stock_zh_index_daily(symbol=symbol)
                if not df.empty:
                    df = df.rename(columns={"date": "date", "close": "close", "high": "high", "low": "low", "open": "open", "volume": "volume"})
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    df_hist = df
            except Exception:
                pass
        
        # 3. Yahoo 兜底 (V15 保留)
        if (df_hist is None or df_hist.empty) and yf:
            try:
                suffix = ".SS" if code.startswith('5') or code.startswith('6') else ".SZ"
                tk = yf.Ticker(code + suffix)
                df = tk.history(period="1y")
                if not df.empty:
                    df = df.rename(columns={"Close": "close", "High": "high", "Low": "low", "Open": "open", "Volume": "volume"})
                    df.index = df.index.tz_localize(None)
                    df_hist = df
            except:
                pass

        if df_hist is None or df_hist.empty: return None

        # 实时缝合
        if self._is_trading_time():
            real_candle = self._fetch_realtime_candle(code)
            if real_candle is not None:
                last_date = df_hist.index[-1]
                today_date = pd.Timestamp(real_candle['date'])
                if last_date != today_date:
                    df_real = pd.DataFrame([real_candle]).set_index('date')
                    df_hist = pd.concat([df_hist, df_real])
                else:
                    df_hist.iloc[-1] = real_candle

        return df_hist
