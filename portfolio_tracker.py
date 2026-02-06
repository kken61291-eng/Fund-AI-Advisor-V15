import json
import os
import threading
from datetime import datetime
from utils import logger

class PortfolioTracker:
    def __init__(self, filepath='portfolio.json'):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            return {"positions": {}, "history": [], "signals": {}}
        try:
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except:
            return {"positions": {}, "history": [], "signals": {}}

    def _save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_position(self, code):
        return self.data['positions'].get(code, {"shares": 0, "cost": 0, "held_days": 0})

    def record_signal(self, code, signal_type):
        today = datetime.now().strftime("%Y-%m-%d")
        if code not in self.data['signals']: self.data['signals'][code] = []
        
        history = self.data['signals'][code]
        # 简单去重
        if not history or history[-1]['date'] != today:
            history.append({"date": today, "s": "B" if "买" in signal_type else ("S" if "卖" in signal_type else "H")})
            # 只保留最近30次
            if len(history) > 30: history.pop(0)
        self._save()

    def add_trade(self, code, name, amount, price, is_sell=False):
        # 简化版持仓更新
        with self.lock:
            pos = self.data['positions'].get(code, {"shares": 0, "cost": 0, "held_days": 0})
            if not is_sell: # 买入
                shares = amount / price
                total_cost = pos['shares'] * pos['cost'] + amount
                pos['shares'] += shares
                pos['cost'] = total_cost / pos['shares']
                pos['held_days'] = 0 # 重置持有天数(简化逻辑)
            else: # 卖出
                pos['shares'] = 0 # 简化：全部清仓
                pos['cost'] = 0
            
            self.data['positions'][code] = pos
            self._save()
    
    def get_signal_history(self, code):
        return self.data['signals'].get(code, [])
    
    def confirm_trades(self):
        # 每日启动时增加持有天数
        for code in self.data['positions']:
            self.data['positions'][code]['held_days'] += 1
        self._save()