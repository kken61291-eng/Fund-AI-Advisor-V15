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
        # 简化版：实际生产中建议使用 akshare，但为防止报错，这里做异常处理
        # 请确保安装了 akshare
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol="要闻")
            raw_list = []
            for _, row in df.iterrows():
                title = str(row.get('title', ''))[:30]
                raw_list.append(f"[{str(row.get('public_time',''))[5:16]}] (东财) {title}")
            return raw_list[:5]
        except:
            return []

    def _fetch_cls_telegraph(self):
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
                        txt = title if title else content[:40]
                        time_str = self._format_short_time(item.get("ctime", 0))
                        raw_list.append(f"[{time_str}] (财社) {txt}")
        except Exception as e:
            logger.warning(f"财社源微瑕: {e}")
        return raw_list

    @retry(retries=2, delay=2)
    def fetch_news_titles(self, keywords_str):
        # 简单融合
        l1 = self._fetch_cls_telegraph()
        l2 = self._fetch_eastmoney_news()
        all_n = l1 + l2
        
        hits = []
        keys = keywords_str.split()
        for n in all_n:
            if any(k in n for k in keys):
                hits.append(n)
        
        return hits[:8] if hits else all_n[:5] # 兜底

    def _clean_json(self, text):
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            return match.group(0) if match else text
        except: return text

    @retry(retries=2, delay=2)
    def analyze_fund_v5(self, fund_name, tech, macro, news, risk):
        # 准备数据
        fuse = risk['fuse_level']
        fuse_msg = risk['risk_msg']
        
        prompt = f"""
        你现在是【玄铁联邦投委会 V15】。
        硬风控状态: 熔断等级 {fuse} (0=正常, 3=空仓)。指令: {fuse_msg}。
        
        标的: {fund_name}
        数据: RSI={tech.get('rsi')}, MACD={tech.get('macd',{}).get('trend')}, VR={tech.get('risk_factors',{}).get('vol_ratio')}
        新闻: {str(news)[:300]}
        
        请进行双盲辩论。
        如果熔断等级>=2，CIO必须驳回买入。
        
        输出JSON:
        {{
            "bull_view": "CGO观点(30字)",
            "bear_view": "CRO观点(30字)",
            "chairman_conclusion": "CIO裁决(50字)",
            "adjustment": 0
        }}
        """
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        
        resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload, timeout=60)
        return json.loads(self._clean_json(resp.json()['choices'][0]['message']['content']))

    # --- [恢复功能] CIO 战略审计 ---
    @retry(retries=2, delay=2)
    def review_report(self, report_text):
        prompt = f"""
        你是【玄铁量化】的 CIO。请对以下汇总进行战略审计（HTML格式）。
        不要废话，直接输出 div class="cio-section" 内容。
        
        汇总数据:
        {report_text}
        
        输出模板:
        <p><strong>宏观定调:</strong> ...</p>
        <p><strong>风控审计:</strong> ...</p>
        <p><strong>最终指令:</strong> ...</p>
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            return resp.json()['choices'][0]['message']['content']
        except:
            return "<p>CIO 审计生成失败</p>"

    # --- [恢复功能] 玄铁先生复盘 ---
    @retry(retries=2, delay=2)
    def advisor_review(self, report_text, macro_str):
        prompt = f"""
        你是【玄铁先生】。请写一段简短的复盘（HTML格式）。
        风格：冷峻、哲学、周期视角。
        
        宏观: {macro_str[:200]}
        决议: {report_text}
        
        输出模板:
        <p><strong>势:</strong> ...</p>
        <p><strong>术:</strong> ...</p>
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            return resp.json()['choices'][0]['message']['content']
        except:
            return "<p>玄铁先生闭关中</p>"
