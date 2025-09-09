# agent_core/prompts/control_prompts.py

"""
控制代理相关提示词
"""


def get_intent_parsing_prompt(user_input: str) -> str:
    """意图解析提示词"""
    return f"""
分析用户的生物医学研究需求，提取实体。

用户输入: {user_input}

返回JSON：
{{
    "entity": {{
        "disease": "疾病或null",
        "target": "基因/靶点或null", 
        "drug": "药物或null",
        "therapy": "治疗方式或null"
    }},
    "scope": ["文献", "临床", "专利"],
    "focus": "一句话总结用户关注点"
}}

只返回JSON。
"""


def get_alias_extraction_prompt(items: list) -> str:
    """别名提取提示词"""
    items_str = "\n".join(items)
    
    return f"""
为以下生物医学术语提供常用别名和同义词：

{items_str}

返回JSON格式：
{{
    "disease": ["别名1", "别名2"],
    "target": ["别名1", "别名2"],
    "drug": ["别名1", "别名2"],
    "therapy": ["别名1", "别名2"]
}}

每个类别最多5个最相关的别名。只返回JSON。
"""