import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time
from utils import logger, get_beijing_time
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from ta.volume import OnBalanceVolumeIndicator

class TechnicalAnalyzer:
    def __init__(self):
        pass

    @staticmethod
    def _calculate_trade_minutes(current_time):
        """计算已交易分钟数"""
        t_min = current_time.hour * 60 + current_time.minute
        t_open_am = 9 * 60 + 30
        t_close_am = 11 * 60 + 30
        t_open_pm = 13 * 60
        t_close_pm = 15 * 60
        
        if t_min < t_open_am: return 0 
        elif t_open_am <= t_min <= t_close_am: return t_min - t_open_am 
        elif t_close_am < t_min < t_open_pm: return 120 
        elif t_open_pm <= t_min <= t_close_pm: return 120 + (t_min - t_open_pm) 
        else: return 240 

    @staticmethod
    def calculate_indicators(df):
        if df is None or df.empty or len(df) < 30: return {}

        # --- [V14.29] 动态量能投影 ---
        try:
            last_date = df.index[-1]
            now_bj = get_beijing_time()
            if last_date.date() == now_bj.date() and now_bj.time() < dt_time(15, 0):
                trade_mins = TechnicalAnalyzer._calculate_trade_minutes(now_bj.time())
                if trade_mins > 15:
                    original_vol = df.iloc[-1]['volume']
                    multiplier = 240 / trade_mins
                    if trade_mins < 120: multiplier *= 0.9 
                    else: multiplier *= 1.05
                    
                    projected_vol = original_vol * multiplier
                    vol_idx = df.columns.get_loc('volume')
                    df.iloc[-1, vol_idx] = projected_vol
        except Exception as e:
            logger.warning(f"量能投影微瑕: {e}")

        indicators = {}
        try:
            df = df.ffill().bfill()
            close = df['close']
            volume = df['volume']
            current_price = close.iloc[-1]
            
            # 1. RSI
            rsi_ind = RSIIndicator(close=close, window=14)
            indicators['rsi'] = round(rsi_ind.rsi().iloc[-1], 2)

            # 2. MACD
            macd_ind = MACD(close=close)
            indicators['macd'] = {
                "line": round(macd_ind.macd().iloc[-1], 3),
                "signal": round(macd_ind.macd_signal().iloc[-1], 3),
                "hist": round(macd_ind.macd_diff().iloc[-1], 3)
            }
            # MACD 趋势判断
            prev_hist = macd_ind.macd_diff().iloc[-2]
            curr_hist = indicators['macd']['hist']
            if curr_hist > 0 and curr_hist < prev_hist: indicators['macd']['trend'] = "红柱缩短"
            elif curr_hist < 0 and curr_hist > prev_hist: indicators['macd']['trend'] = "绿柱缩短"
            else: indicators['macd']['trend'] = "金叉" if curr_hist > 0 else "死叉"

            # 3. Bollinger
            bb_ind = BollingerBands(close=close)
            indicators['risk_factors'] = {
                "bollinger_pct_b": round(bb_ind.bollinger_pband().iloc[-1], 2)
            }

            # 4. VR & OBV
            ma_vol_5 = volume.rolling(window=5).mean().iloc[-1]
            vol_ratio = volume.iloc[-1] / ma_vol_5 if ma_vol_5 > 0 else 1.0
            indicators['risk_factors']['vol_ratio'] = round(vol_ratio, 2)
            
            obv_ind = OnBalanceVolumeIndicator(close=close, volume=volume)
            obv = obv_ind.on_balance_volume()
            obv_slope = (obv.iloc[-1] - obv.iloc[-10]) / 10 if len(obv) > 10 else 0
            indicators['flow'] = {"obv_slope": round(obv_slope / 10000, 2)}

            # 5. 周线趋势 (MA5)
            df_weekly = df.resample('W').agg({'close': 'last'})
            if len(df_weekly) >= 5:
                ma5_weekly = df_weekly['close'].rolling(5).mean().iloc[-1]
                indicators['trend_weekly'] = "UP" if df_weekly['close'].iloc[-1] > ma5_weekly else "DOWN"
            else:
                indicators['trend_weekly'] = "Unknown"
            
            indicators['price'] = current_price
            
            # 6. 涨跌幅 (用于熔断)
            if len(df) >= 2:
                indicators['pct_change'] = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]
            else:
                indicators['pct_change'] = 0.0

            return indicators

        except Exception as e:
            logger.error(f"指标计算失败: {e}")
            return {}