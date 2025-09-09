# agent_core/prompts/clinical_prompts.py

"""
临床试验分析提示词
"""


def get_trial_analysis_prompt(entity: Any, trials_data: str) -> str:
    """临床试验分析提示词"""
    
    entity_desc = []
    if entity.disease:
        entity_desc.append(f"疾病: {entity.disease}")
    if entity.target:
        entity_desc.append(f"靶点: {entity.target}")
    if entity.therapy:
        entity_desc.append(f"治疗: {entity.therapy}")
    
    entity_str = ", ".join(entity_desc) if entity_desc else "未指定"
    
    return f"""
基于以下临床试验数据，分析{entity_str}的临床研究进展。

临床试验数据：
{trials_data}

请分析：
1. 试验分期分布（I/II/III/IV期）
2. 主要研究机构和地理分布
3. 主要终点和疗效指标
4. 安全性信号
5. 关键试验总结

返回结构化分析结果。
"""


def get_trial_trend_prompt(trials_summary: str) -> str:
    """临床试验趋势分析提示词"""
    return f"""
基于以下临床试验汇总，分析研究趋势：

{trials_summary}

请分析：
1. 年度趋势（试验数量变化）
2. 热点适应症
3. 新兴治疗策略
4. 竞争格局
5. 未来发展方向

提供洞察性分析。
"""