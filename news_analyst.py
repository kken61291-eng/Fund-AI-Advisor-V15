import requests
import json
import os
import re
from datetime import datetime
from utils import logger, retry

class NewsAnalyst:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.cls_headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.cls.cn/telegraph",
            "Origin": "https://www.cls.cn"
        }

    def _format_short_time(self, time_str):
        try:
            if str(time_str).isdigit():
                dt = datetime.fromtimestamp(int(time_str))
                return dt.strftime("%m-%d %H:%M")
            if len(str(time_str)) > 10:
                dt = datetime.strptime(str(time_str), "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%m-%d %H:%M")
            return str(time_str)
        except:
            return str(time_str)[:11]

    def _fetch_eastmoney_news(self):
        # Akshare 兜底获取
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol="要闻")
            raw_list = []
            for _, row in df.iterrows():
                title = str(row.get('title', ''))[:40]
                raw_list.append(f"[{str(row.get('public_time',''))[5:16]}] (东财) {title}")
            return raw_list[:5]
        except:
            return []

    def _fetch_cls_telegraph(self):
        # 财联社原生直连
        raw_list = []
        url = "https://www.cls.cn/nodeapi/telegraphList"
        params = {"rn": 20, "sv": 7755}
        try:
            resp = requests.get(url, headers=self.cls_headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and "roll_data" in data["data"]:
                    for item in data["data"]["roll_data"]:
                        title = item.get("title", "")
                        content = item.get("content", "")
                        txt = title if title else content[:50]
                        time_str = self._format_short_time(item.get("ctime", 0))
                        raw_list.append(f"[{time_str}] (财社) {txt}")
        except Exception as e:
            logger.warning(f"财社源微瑕: {e}")
        return raw_list

    @retry(retries=2, delay=2)
    def fetch_news_titles(self, keywords_str):
        l1 = self._fetch_cls_telegraph()
        l2 = self._fetch_eastmoney_news()
        all_n = l1 + l2
        
        hits = []
        keys = keywords_str.split()
        seen = set()
        
        for n in all_n:
            # 简单去重
            clean_n = n.split(']')[-1].strip()
            if clean_n in seen: continue
            seen.add(clean_n)
            
            if any(k in n for k in keys):
                hits.append(n)
        
        # 兜底：如果没有命中，返回财社最新的3条
        return hits[:8] if hits else l1[:3]

    def _clean_json(self, text):
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            return match.group(0) if match else "{}"
        except: return "{}"

    @retry(retries=2, delay=2)
    def analyze_fund_v5(self, fund_name, tech, macro, news, risk):
        # 准备数据
        fuse = risk['fuse_level']
        fuse_msg = risk['risk_msg']
        
        # 数据提取
        trend = tech.get('trend_weekly', '无趋势')
        rsi = tech.get('rsi', 50)
        macd = tech.get('macd', {})
        macd_str = f"{macd.get('trend','N/A')} (Hist:{macd.get('hist',0)})"
        
        flow = tech.get('flow', {})
        obv = flow.get('obv_slope', 0)
        money_flow = "抢筹" if obv > 1 else ("出逃" if obv < -1 else "博弈")
        
        vol_ratio = tech.get('risk_factors', {}).get('vol_ratio', 1.0)
        vol_str = "放量" if vol_ratio > 1.2 else ("缩量" if vol_ratio < 0.8 else "温和")

        # 完整 Prompt (未删减)
        prompt = f"""
        你现在是【玄铁联邦投委会 V15】。
        请基于【全息档案】和【硬风控结论】，进行"双盲辩论"并"强制收敛"。

        🔴 **【最高宪法·硬风控结论】(The Iron Fist)**:
        - 熔断等级: {fuse}级 (0=正常, 1=预警, 2=限制, 3=空仓)
        - 风控官指令: {fuse_msg}
        - (注意: 如果熔断等级>=2，CIO必须无条件服从风控指令，驳回所有进攻建议)

        📁 **公开·全息档案 (Blind Data)**:
        - 标的: {fund_name}
        - 周线趋势: {trend}
        - MACD状态: {macd_str}
        - RSI(14): {rsi}
        - 资金意图: {money_flow} (OBV斜率:{obv:.2f})
        - 量能状态: {vol_str} (VR:{vol_ratio})

        📰 **自查情报**:
        - 宏观: {macro[:300]}
        - 本地新闻: {str(news)[:400]}

        --- 🏛️ 参会人员与人设 ---

        1. **🦊 CGO (增长官)** - [盲评模式]
           - **人设**: 激进的动量交易者，信仰趋势。
           - **任务**: 寻找一切做多理由。
           - **底线**: 如果MACD死叉且量能枯竭，必须**诚实地放弃抵抗**。

        2. **🐻 CRO (风控官)** - [盲评模式]
           - **人设**: 谨慎的空头，信仰均值回归。
           - **任务**: 寻找一切风险点。
           - **底线**: 如果量价齐升且估值低，必须**诚实地承认**安全。

        3. **⚖️ CIO (首席投资官)** - [华尔街老兵]
           - **人设**: 穿越过2008年危机的老兵。拥有独立嗅觉。
           - **任务**: 
             1. **反身性思考**: 利好是否已Price-in？恐慌是否是黄金坑？
             2. **降维打击**: 如果熔断触发，直接执行风控指令。
           - **最终决策**: 必须给出统一结论（攻或守）。

        --- 输出要求 (JSON) ---
        {{
            "bull_view": "CGO: (引用数据)... 观点 (30字)",
            "bear_view": "CRO: (引用数据)... 观点 (30字)",
            "chairman_conclusion": "CIO: [华尔街视角+硬风控]... 最终修正 (50字)",
            "adjustment": 整数数值 (-30 到 +30),
            "risk_alert": "核心风险点"
        }}
        """
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_tokens": 1000
        }
        
        resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=60)
        return json.loads(self._clean_json(resp.json()['choices'][0]['message']['content']))

    # --- 完整的 CIO 战略审计 ---
    @retry(retries=2, delay=2)
    def review_report(self, report_text):
        prompt = f"""
        你是【玄铁量化】的 CIO。请对以下汇总进行【战略审计】，输出 HTML。
        内容要求：言简意赅，直击痛点，不要废话。
        
        汇总数据:
        {report_text}
        
        输出模板:
        <div class="cio-section">
            <h3 style="border-left: 4px solid #d32f2f; padding-left: 10px;">宏观定调</h3>
            <p>(基于数据给出一句定性)</p>
            <h3 style="border-left: 4px solid #d32f2f; padding-left: 10px;">双轨审计</h3>
            <p>(指出哪个基金表现异常)</p>
            <h3 style="border-left: 4px solid #d32f2f; padding-left: 10px;">CIO指令</h3>
            <p>(给出总仓位建议)</p>
        </div>
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            clean = self._clean_html(resp.json()['choices'][0]['message']['content'])
            return clean
        except:
            return "<p>CIO 审计生成失败</p>"

    # --- 完整的玄铁先生复盘 ---
    @retry(retries=2, delay=2)
    def advisor_review(self, report_text, macro_str):
        prompt = f"""
        你是 **【玄铁先生】**，一位冷峻的市场哲学家。
        请写一段【场外实战复盘】 (HTML)。
        风格：使用短句，富有哲理，关注周期与人性。
        
        宏观: {macro_str[:200]}
        决议: {report_text}
        
        输出模板:
        <div class="advisor-section">
            <h4 style="color: #ffd700;">【势·验证】</h4><p>...</p>
            <h4 style="color: #ffd700;">【术·底仓】</h4><p>...</p>
            <h4 style="color: #ffd700;">【断·进攻】</h4><p>...</p>
        </div>
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            clean = self._clean_html(resp.json()['choices'][0]['message']['content'])
            return clean
        except:
            return "<p>玄铁先生闭关中</p>"
            
    def _clean_html(self, text):
        text = text.replace("```html", "").replace("```", "").strip()
        return text
