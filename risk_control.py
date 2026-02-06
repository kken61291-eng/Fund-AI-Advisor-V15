from utils import logger

class RiskController:
    """
    [V15 铁腕风控]
    独立于AI之外的数学宪法。
    职责：
    1. 判定市场波动率等级 (Dynamic Threshold)
    2. 执行三级熔断检查 (Circuit Breaker)
    3. 给出硬性头寸限制 (Position Constraint)
    """
    def __init__(self, config):
        self.config = config.get('global', {}).get('risk_control', {})
        self.fuse_1 = self.config.get('fuse_level_1_drop', -0.02)
        self.fuse_2 = self.config.get('fuse_level_2_drop', -0.04)
        self.fuse_3 = self.config.get('fuse_level_3_drop', -0.06)

    def analyze_risk(self, fund_name, tech_indicators, volatility):
        """
        全流程风控检查
        返回: {
            "fuse_level": 0/1/2/3,
            "max_position_ratio": 1.0 ~ 0.0,
            "risk_msg": "描述信息"
        }
        """
        pct_change = tech_indicators.get('pct_change', 0.0)
        vol_ratio = tech_indicators.get('risk_factors', {}).get('vol_ratio', 1.0)
        
        result = {
            "fuse_level": 0,
            "max_position_ratio": 1.0,
            "risk_msg": "风控正常"
        }

        # 1. 动态阈值调整
        # 如果市场波动率很高(>3%)，我们要求更严格的买入标准
        # (此处逻辑可扩展，目前主要影响熔断敏感度，暂时保持硬阈值)
        
        # 2. 三级熔断检查
        
        # [三级熔断] 强制空仓
        if pct_change <= self.fuse_3:
            result["fuse_level"] = 3
            result["max_position_ratio"] = 0.0
            result["risk_msg"] = f"触发三级熔断(跌幅{pct_change:.2%})，强制空仓"
            logger.critical(f"🛑 [{fund_name}] {result['risk_msg']}")
            return result

        # [二级熔断] 限制买入 (只允许定投，禁止重仓)
        if pct_change <= self.fuse_2:
            result["fuse_level"] = 2
            result["max_position_ratio"] = 0.2
            result["risk_msg"] = f"触发二级熔断(跌幅{pct_change:.2%})，禁止重仓"
            logger.warning(f"⚠️ [{fund_name}] {result['risk_msg']}")
            return result

        # [一级熔断] 缩量阴跌预警
        if pct_change < -0.015 and vol_ratio < 0.7:
            result["fuse_level"] = 1
            result["max_position_ratio"] = 0.5
            result["risk_msg"] = f"触发一级熔断(缩量阴跌 VR{vol_ratio})，谨慎行事"
            logger.warning(f"🛡️ [{fund_name}] {result['risk_msg']}")
            return result

        # 3. 波动率过滤
        # 如果是大盘低波动的垃圾时间，建议少动
        if volatility < 0.005: # 0.5% 波动率，死水一潭
            result["risk_msg"] = "市场波动率极低，处于垃圾时间，建议观望"
            # 不强制熔断，但提示
        
        return result