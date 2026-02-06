import yaml
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import DataFetcher
from technical_analyzer import TechnicalAnalyzer
from news_analyst import NewsAnalyst
from risk_control import RiskController
from valuation_engine import ValuationEngine
from portfolio_tracker import PortfolioTracker
from utils import send_email, logger

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# --- [V15 UI 终极渲染引擎] 100% 还原 V14 细节并融合 V15 风控 ---
def render_html_report_v15_full(all_news, results, cio_html, advisor_html, volatility):
    # 1. 新闻雷达 (支持去重与高亮)
    news_html = ""
    seen_titles = set()
    unique_news = []
    for n in all_news:
        # 简单去重逻辑
        raw_t = n.split(']')[-1].strip() if ']' in n else n
        if raw_t not in seen_titles:
            unique_news.append(n)
            seen_titles.add(raw_t)
    
    # 排序：突发/财社新闻置顶
    unique_news.sort(key=lambda x: (not ('财社' in x or '突发' in x or '重磅' in x)), reverse=False)

    for news in unique_news[:18]: # 展示更多新闻
        color = "#ffb74d" if ('财社' in news or '突发' in news) else "#999"
        news_html += f"""
        <div style="font-size:11px;color:#ccc;margin-bottom:5px;border-bottom:1px dashed #333;padding-bottom:3px;">
            <span style="color:{color};margin-right:4px;">●</span>{news}
        </div>
        """

    # 2. 历史信号点阵渲染 (V14遗失功能回归)
    def render_dots(hist):
        h = ""
        # 取最近15次记录
        for x in hist[-15:]:
            c = "#d32f2f" if x['s']=='B' else ("#388e3c" if x['s'] in ['S','C'] else "#555")
            h += f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{c};margin-right:3px;box-shadow:0 0 2px rgba(0,0,0,0.5);" title="{x["date"]}"></span>'
        return h

    # 3. 基金卡片渲染
    rows = ""
    for r in results:
        try:
            tech = r.get('tech', {})
            risk = r.get('risk', {})
            ai = r.get('ai', {})
            pos_info = r.get('position_info', {}) # 持仓数据
            
            score = r.get('score', 0)
            fuse_level = risk.get('fuse_level', 0)
            risk_msg = risk.get('risk_msg', '正常')
            
            # --- 颜色与徽章逻辑 ---
            if fuse_level >= 3: 
                border_color = "#b71c1c"
                bg_gradient = "linear-gradient(90deg, rgba(60,0,0,0.9) 0%, rgba(20,20,20,0.95) 100%)"
                badge_html = "<span style='background:#b71c1c;color:white;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:bold;'>⛔ 熔断 Lv3 (强制空仓)</span>"
            elif fuse_level == 2:
                border_color = "#e65100"
                bg_gradient = "linear-gradient(90deg, rgba(60,30,0,0.9) 0%, rgba(20,20,20,0.95) 100%)"
                badge_html = "<span style='background:#e65100;color:white;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:bold;'>⚠️ 熔断 Lv2 (禁止重仓)</span>"
            elif fuse_level == 1:
                border_color = "#fbc02d"
                bg_gradient = "linear-gradient(90deg, rgba(40,40,0,0.9) 0%, rgba(20,20,20,0.95) 100%)"
                badge_html = "<span style='background:#fbc02d;color:black;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:bold;'>🛡️ 熔断 Lv1 (预警)</span>"
            else:
                border_color = "#2e7d32" if r['action'] == "买入" else "#555"
                bg_gradient = "linear-gradient(90deg, rgba(10,40,10,0.9) 0%, rgba(20,20,20,0.95) 100%)" if r['action'] == "买入" else "linear-gradient(90deg, rgba(30,30,30,0.9) 0%, rgba(15,15,15,0.95) 100%)"
                badge_html = "<span style='background:#2e7d32;color:white;padding:2px 6px;border-radius:3px;font-size:10px;'>✅ 风控正常</span>"

            # --- 持仓收益逻辑 (V14遗失功能回归) ---
            profit_html = ""
            if pos_info.get('shares', 0) > 0:
                cost = pos_info['cost']
                curr = tech.get('price', 0)
                if cost > 0:
                    profit_pct = (curr - cost) / cost * 100
                    profit_val = (curr - cost) * pos_info['shares']
                    p_color = "#ff5252" if profit_val > 0 else "#69f0ae"
                    profit_html = f"""
                    <div style="font-size:12px;margin-bottom:8px;background:rgba(255,255,255,0.05);padding:4px 8px;border-radius:3px;display:flex;justify-content:space-between;">
                        <span style="color:#aaa;">持仓成本: {cost:.3f}</span>
                        <span style="color:{p_color};font-weight:bold;">{profit_val:+.1f}元 ({profit_pct:+.2f}%)</span>
                    </div>
                    """

            # --- 辩论与裁决 ---
            bull_say = ai.get('bull_say', 'N/A')
            bear_say = ai.get('bear_say', 'N/A')
            cio_say = ai.get('comment', 'N/A')
            adj = ai.get('adjustment', 0)
            
            # CIO 修正分颜色
            adj_color = "#ff5252" if adj > 0 else ("#69f0ae" if adj < 0 else "#ccc")

            committee_html = ""
            if bull_say != 'N/A':
                committee_html = f"""
                <div style="margin-top:12px;border-top:1px solid #444;padding-top:10px;">
                    <div style="font-size:10px;color:#888;margin-bottom:6px;text-align:center;">--- V15 铁腕联邦投委会 ---</div>
                    <div style="display:flex;gap:10px;margin-bottom:8px;">
                        <div style="flex:1;background:rgba(27,94,32,0.2);padding:8px;border-radius:4px;border-left:2px solid #66bb6a;">
                            <div style="color:#66bb6a;font-size:11px;font-weight:bold;margin-bottom:4px;">🦊 CGO (增长)</div>
                            <div style="color:#c8e6c9;font-size:11px;line-height:1.3;font-style:italic;">"{bull_say}"</div>
                        </div>
                        <div style="flex:1;background:rgba(183,28,28,0.2);padding:8px;border-radius:4px;border-left:2px solid #ef5350;">
                            <div style="color:#ef5350;font-size:11px;font-weight:bold;margin-bottom:4px;">🐻 CRO (风控)</div>
                            <div style="color:#ffcdd2;font-size:11px;line-height:1.3;font-style:italic;">"{bear_say}"</div>
                        </div>
                    </div>
                    <div style="background:linear-gradient(90deg, rgba(255,183,77,0.1) 0%, rgba(255,183,77,0.05) 100%);padding:10px;border-radius:4px;border:1px solid rgba(255,183,77,0.3);position:relative;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                            <div style="color:#ffb74d;font-size:12px;font-weight:bold;">⚖️ CIO 终审 (华尔街视角)</div>
                            <div style="color:{adj_color};font-size:11px;font-weight:bold;">修正: {adj:+d}</div>
                        </div>
                        <div style="color:#fff3e0;font-size:12px;line-height:1.4;">{cio_say}</div>
                    </div>
                </div>
                """
            else:
                 committee_html = f"<div style='color:#f44336;font-size:12px;margin-top:10px;'>⚠️ AI 未生成有效辩论 (API Error)</div>"

            # --- 硬指标 ---
            vol_ratio = tech.get('risk_factors', {}).get('vol_ratio', 0)
            rsi = tech.get('rsi', 0)
            macd_trend = tech.get('macd', {}).get('trend', 'N/A')
            
            # 交易动作颜色
            act_html = ""
            if r['action'] == "买入":
                act_html = f"<span style='color:#ff8a80;font-weight:bold;font-size:14px;'>+{r['amount']:,}</span>"
            elif r['action'] == "卖出":
                act_html = f"<span style='color:#a5d6a7;font-weight:bold;font-size:14px;'>SELL</span>"
            else:
                act_html = "<span style='color:#777;font-size:14px;'>HOLD</span>"

            rows += f"""
            <div style="background:{bg_gradient};border-left:4px solid {border_color};margin-bottom:15px;padding:15px;border-radius:6px;box-shadow:0 4px 10px rgba(0,0,0,0.6);border-top:1px solid #333;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <div>
                        <span style="font-size:18px;font-weight:bold;color:#f0e6d2;font-family:'Times New Roman',serif;">{r['name']}</span>
                        <span style="margin-left:8px;">{badge_html}</span>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#ffb74d;font-weight:bold;font-size:16px;text-shadow:0 0 5px rgba(255,183,77,0.3);">{score} 分</div>
                        <div style="font-size:10px;color:#aaa;">{r['action']} | {act_html}</div>
                    </div>
                </div>
                
                {profit_html}

                <div style="background:rgba(0,0,0,0.3);padding:6px 10px;border-radius:4px;margin-bottom:10px;display:flex;align-items:center;border-left:2px solid {border_color};">
                    <span style="font-size:11px;color:#aaa;margin-right:8px;">🛑 铁腕风控:</span>
                    <span style="font-size:11px;color:#fff;font-weight:bold;">{risk_msg}</span>
                </div>

                <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:5px;font-size:11px;color:#bdbdbd;font-family:'Courier New',monospace;margin-bottom:8px;">
                    <span>RSI: {rsi}</span>
                    <span>MACD: {macd_trend}</span>
                    <span>VR: {vol_ratio}</span>
                    <span>Wkly: {tech.get('trend_weekly','-')}</span>
                </div>
                
                <div style="margin-top:5px;margin-bottom:5px;">{render_dots(r.get('history', []))}</div>
                
                {committee_html}
            </div>
            """
        except Exception as e:
            logger.error(f"渲染卡片失败 {r.get('name')}: {e}")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
        body {{ background: #0a0a0a; color: #f0e6d2; font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; max-width: 660px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 25px; }}
        .title {{ color: #ffb74d; margin: 0; font-size: 32px; font-weight: 800; font-family: 'Times New Roman', serif; letter-spacing: 2px; }}
        .subtitle {{ font-size: 11px; color: #888; margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }}
        .radar-panel {{ background: #111; border: 1px solid #333; border-radius: 4px; padding: 15px; margin-bottom: 25px; }}
        .radar-title {{ font-size: 14px; color: #ffb74d; font-weight: bold; margin-bottom: 12px; border-bottom: 1px solid #444; padding-bottom: 6px; letter-spacing: 1px; }}
        .cio-section {{ background: linear-gradient(145deg, #1a0505, #2b0b0b); border: 1px solid #5c1818; border-left: 4px solid #d32f2f; padding: 20px; margin-bottom: 20px; border-radius: 2px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }}
        .cio-section p, .cio-section div, .cio-section h3 {{ color: #ffffff !important; line-height: 1.6; }}
        .advisor-section {{ background: #0f0f0f; border: 1px solid #d4af37; border-left: 4px solid #ffd700; padding: 20px; margin-bottom: 30px; border-radius: 4px; box-shadow: 0 0 10px rgba(212, 175, 55, 0.2); }}
        .advisor-section * {{ color: #ffffff !important; line-height: 1.6; font-family: 'Georgia', serif; }}
        .footer {{ text-align: center; font-size: 10px; color: #444; margin-top: 40px; }}
    </style></head><body>
        <div class="header">
            <h1 class="title">XUANTIE V15</h1>
            <div class="subtitle">IRON FIST RISK CONTROL | VOLATILITY: {volatility:.2%}</div>
        </div>
        
        <div class="radar-panel">
            <div class="radar-title">📡 V15 全球情报雷达 (双源融合)</div>
            {news_html}
        </div>

        <div class="cio-section">
            <div style="font-size:16px;font-weight:bold;margin-bottom:15px;color:#eee;text-transform:uppercase;">🛑 CIO 战略审计 (V15)</div>
            {cio_html}
        </div>

        <div class="advisor-section">
            <div style="font-size:16px;font-weight:bold;margin-bottom:15px;color:#ffd700;">🗡️ 玄铁先生复盘</div>
            {advisor_html}
        </div>

        {rows}
        <div class="footer">EST. 2026 | POWERED BY IRON FIST ALGORITHM</div>
    </body></html>"""

def process_fund(fund, config, fetcher, risk_ctrl, analyst, tracker, val_engine, macro_news, volatility):
    try:
        logger.info(f"⚔️ [V15处理] 启动分析 {fund['name']}...")
        
        # 1. 获取数据
        df = fetcher.get_fund_history(fund['code'])
        if df is None: return None, []

        # 2. 技术分析
        tech = TechnicalAnalyzer.calculate_indicators(df)
        
        # 3. 硬风控 (Iron Fist)
        risk_assessment = risk_ctrl.analyze_risk(fund['name'], tech, volatility)
        fuse_level = risk_assessment['fuse_level']
        max_pos_ratio = risk_assessment['max_position_ratio']
        
        # 4. 获取持仓信息 (用于UI显示收益)
        with tracker.lock:
            pos_info = tracker.get_position(fund['code'])
        
        # 5. 情报与辩论
        ai_res = {}
        keyword = fund.get('sector_keyword', fund['name'])
        news = []
        
        if analyst:
            news = analyst.fetch_news_titles(keyword)
            try:
                # 传入 risk_assessment，让 AI 知道风控状态
                ai_res = analyst.analyze_fund_v5(fund['name'], tech, macro_news, news, risk_assessment)
            except Exception as e:
                logger.error(f"AI分析失败 {fund['name']}: {e}")
                # 即使失败，也要返回基础数据，保证卡片能渲染
                ai_res = {"bull_say": "API Error", "bear_say": "API Error", "comment": "手动检查", "adjustment": 0}
        
        # 6. 决策收敛
        base_score = tech.get('quant_score', 50)
        ai_adj = ai_res.get('adjustment', 0)
        
        # 硬风控介入：如果熔断，强制压低分数
        if fuse_level >= 2:
            ai_adj = -50 
            
        final_score = base_score + ai_adj
        final_score = max(0, min(100, final_score))
        
        # 7. 计算买卖
        action = "观望"
        amount = 0
        base_invest = config['global']['base_invest_amount']
        
        if final_score >= 70 and fuse_level < 2:
            action = "买入"
            amount = int(base_invest * max_pos_ratio)
        elif final_score <= 30 or fuse_level >= 3:
            action = "卖出"
            
        # 8. 记录信号与交易
        with tracker.lock:
            tracker.record_signal(fund['code'], action)
            if amount > 0:
                tracker.add_trade(fund['code'], fund['name'], amount, tech['price'])
            # 增加 history 用于 UI 点阵渲染
            signal_history = tracker.get_signal_history(fund['code'])

        res = {
            "name": fund['name'],
            "score": final_score,
            "action": action,
            "amount": amount,
            "risk": risk_assessment,
            "ai": ai_res,
            "tech": tech,
            "history": signal_history, # 传给 UI
            "position_info": pos_info  # 传给 UI
        }
        return res, news
    except Exception as e:
        logger.error(f"处理基金 {fund['name']} 严重错误: {e}")
        return None, []

def main():
    logger.info(">>> 🚀 玄铁量化 V15.0 (Iron Fist) 启动...")
    config = load_config()
    
    fetcher = DataFetcher()
    risk_ctrl = RiskController(config)
    analyst = NewsAnalyst()
    tracker = PortfolioTracker()
    val_engine = ValuationEngine()
    
    volatility = fetcher.get_market_volatility()
    macro_news = analyst.fetch_news_titles("宏观 A股 美联储")
    # 构造宏观字符串，用于 AI 上下文
    macro_str = " | ".join([n.split(']')[-1] for n in macro_news[:5]])
    
    results = []
    all_news = []
    all_news.extend(macro_news)
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_fund, f, config, fetcher, risk_ctrl, analyst, tracker, val_engine, macro_str, volatility): f for f in config['funds']}
        
        for future in as_completed(futures):
            res, fund_news = future.result()
            if res:
                results.append(res)
                all_news.extend(fund_news)

    # 生成总结报告
    if results:
        # 简单的总结文本用于生成 CIO 和 顾问报告
        summary_text = "\n".join([f"{r['name']}: {r['action']} (分:{r['score']} 熔断Lv:{r['risk']['fuse_level']})" for r in results])
        
        try:
            cio_html = analyst.review_report(summary_text)
            advisor_html = analyst.advisor_review(summary_text, macro_str)
        except Exception as e:
            logger.error(f"生成汇总失败: {e}")
            cio_html = "<p>CIO 忙碌中...</p>"
            advisor_html = "<p>玄铁先生闭关中...</p>"
            
        html_report = render_html_report_v15_full(all_news, results, cio_html, advisor_html, volatility)
        send_email("玄铁 V15 决策报告 (Iron Fist)", html_report)
    else:
        logger.warning("无有效结果生成")
        
    logger.info("✅ 任务完成")

if __name__ == "__main__":
    main()
