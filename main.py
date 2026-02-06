import yaml
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import DataFetcher
from technical_analyzer import TechnicalAnalyzer
from news_analyst import NewsAnalyst
from risk_control import RiskController # [V15 新增]
from valuation_engine import ValuationEngine
from portfolio_tracker import PortfolioTracker
from utils import send_email, logger

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def process_fund(fund, config, fetcher, risk_ctrl, analyst, tracker, val_engine, macro_news, volatility):
    logger.info(f"⚔️ [V15处理] 启动分析 {fund['name']}...")
    
    # 1. 获取数据
    df = fetcher.get_fund_history(fund['code'])
    if df is None: return None

    # 2. 技术分析 (含动态量能投影)
    tech = TechnicalAnalyzer.calculate_indicators(df)
    
    # 3. [V15 核心] 硬风控检查 (The Iron Fist)
    risk_assessment = risk_ctrl.analyze_risk(fund['name'], tech, volatility)
    fuse_level = risk_assessment['fuse_level']
    max_pos_ratio = risk_assessment['max_position_ratio']
    
    # 4. 情报与辩论 (仅当未完全熔断时深入分析)
    # 即使熔断，也让 AI 跑一下，生成"防守报告"，但不执行买入
    ai_res = {}
    keyword = fund.get('sector_keyword', fund['name'])
    
    if analyst:
        # 抓新闻
        news = analyst.fetch_news_titles(keyword)
        # 传入 risk_assessment 让 CIO 知道风控状态
        ai_res = analyst.analyze_fund_v5(fund['name'], tech, macro_news, news, risk_assessment)
    else:
        news = []

    # 5. 最终决策收敛
    base_score = tech.get('quant_score', 50)
    ai_adj = ai_res.get('adjustment', 0)
    
    # 如果触发硬风控，强制压低分数
    if fuse_level >= 2:
        logger.warning(f"🛑 {fund['name']} 处于熔断状态(Lv{fuse_level})，强制修正 AI 得分")
        ai_adj = -50 # 强制扣分
        
    final_score = base_score + ai_adj
    final_score = max(0, min(100, final_score))
    
    # 6. 计算买卖
    action = "观望"
    amount = 0
    
    # 简单的买卖映射
    base_invest = config['global']['base_invest_amount']
    
    if final_score >= 70 and fuse_level < 2:
        action = "买入"
        # 头寸受硬风控限制
        amount = int(base_invest * max_pos_ratio)
    elif final_score <= 30 or fuse_level >= 3:
        action = "卖出" # 或清仓
        
    # 记录
    res = {
        "name": fund['name'],
        "score": final_score,
        "action": action,
        "amount": amount,
        "risk": risk_assessment,
        "ai": ai_res,
        "tech": tech
    }
    return res, news

def main():
    logger.info(">>> 🚀 玄铁量化 V15.0 (Iron Fist) 启动...")
    config = load_config()
    
    fetcher = DataFetcher()
    risk_ctrl = RiskController(config) # V15
    analyst = NewsAnalyst()
    tracker = PortfolioTracker()
    val_engine = ValuationEngine()
    
    # 1. 获取全局宏观数据
    volatility = fetcher.get_market_volatility() # V15 新增
    macro_news = analyst.fetch_news_titles("宏观 A股 美联储")
    macro_str = " | ".join(macro_news)
    
    results = []
    all_news = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_fund, f, config, fetcher, risk_ctrl, analyst, tracker, val_engine, macro_str, volatility): f for f in config['funds']}
        
        for future in as_completed(futures):
            try:
                res, news = future.result()
                if res:
                    results.append(res)
                    all_news.extend(news)
            except Exception as e:
                logger.error(f"处理异常: {e}")

    # 生成简报 (这里简化 HTML 生成，重点在于逻辑)
    report = f"<h1>玄铁量化 V15 (Iron Fist)</h1><p>市场波动率: {volatility:.2%}</p>"
    for r in results:
        color = "red" if r['action'] == "买入" else "green"
        report += f"""
        <div style='border:1px solid #ccc; padding:10px; margin:5px;'>
            <h3>{r['name']} <span style='color:{color}'>{r['action']}</span></h3>
            <p>得分: {r['score']} (熔断Lv: {r['risk']['fuse_level']})</p>
            <p>风控: {r['risk']['risk_msg']}</p>
            <p>CIO: {r['ai'].get('comment', '')}</p>
        </div>
        """
    
    send_email("玄铁 V15 决策报告", report)
    logger.info("✅ 任务完成")

if __name__ == "__main__":
    main()