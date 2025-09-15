# agent_core/prompts/control_prompts.py

"""
Control Agent 提示词模板
"""

def get_intent_parsing_prompt(user_input: str) -> str:
        """
        统一的意图解析、实体提取、专家选择提示词
        一次LLM调用完成所有解析任务
        """
        return f"""
    你是一个生物医学研究助手的中央控制系统。请分析用户的查询需求，并完成以下三个任务：

    ## 用户输入
    {user_input}

    ## 任务1：意图分类（Intent Classification）
    判断用户查询属于以下哪种类型：

    ### intent_type定义：
    1. **report**: 用户需要完整的调研报告
    - 特征：要求全面分析、综合报告、详细调研、完整信息
    - 示例："帮我调研PD-1靶点"、"分析EGFR在肺癌中的应用"、"做一份CAR-T治疗的完整报告"

    2. **qa_external**: 需要查询外部数据源的具体问题
    - 特征：具体的问题、需要最新数据、特定信息查询
    - 示例："PD-1抗体最新的临床试验进展？"、"KRAS G12C抑制剂有哪些？"、"这个靶点的专利情况如何？"

    3. **qa_internal**: 基于已有报告/对话历史的问题（无需调用子专家）
    - 特征：追问之前的内容、要求解释报告中的某部分、基于已有信息的问题
    - 示例："刚才提到的副作用具体是什么？"、"报告中的三期临床数据能详细说说吗？"、"上面的专利是哪家公司的？"

    4. **target_comparison**: 多个靶点或方案的对比分析
    - 特征：对比、比较、优劣分析、选择建议
    - 示例："对比PD-1和PD-L1的优劣"、"EGFR和ALK哪个靶点更有前景？"、"比较这三种CAR-T疗法"

    ## 任务2：实体提取（Entity Extraction）
    从用户输入中提取以下实体（没有的字段设为null）：

    - **target/gene**: 基因名、靶点名、蛋白名（如：PD-1, EGFR, KRAS G12C, CD19）
    - **disease**: 疾病名称（如：肺癌、白血病、阿尔茨海默症）
    - **drug**: 具体药物名称（如：Keytruda、信迪利单抗、奥希替尼）
    - **therapy**: 治疗方式（如：CAR-T、单抗、小分子抑制剂、细胞治疗）

    ## 任务3：专家选择（Expert Selection）
    根据查询需求，从以下可用专家中选择需要调用的专家（仅当intent_type不是qa_internal时）：

    ### 可用专家列表：
    - **literature_expert**: 文献调研专家（PubMed、学术论文、研究进展）
    - **clinical_expert**: 临床试验专家（ClinicalTrials.gov、临床数据、试验进展）
    - **patent_expert**: 专利分析专家（专利数据库、知识产权、技术布局）
    - **market_expert**: 市场分析专家（市场规模、竞争格局、商业化）

    ### 选择原则：
    - report类型：通常需要所有相关专家
    - qa_external类型：只选择1-3个最相关的专家
    - qa_internal类型：不需要任何专家（返回空列表）
    - target_comparison类型：根据对比维度选择相关专家

    ## 输出格式
    请严格按照以下JSON格式返回（仅返回JSON，无其他内容）：
    ```json
    {{
        "intent_type": "report/qa_external/qa_internal/target_comparison",
        "confidence": 0.0-1.0,
        "entities": {{
            "target": "提取的靶点/基因名或null",
            "disease": "提取的疾病名或null",
            "drug": "提取的药物名或null", 
            "therapy": "提取的治疗方式或null"
        }},
        "relevant_experts": ["expert1", "expert2"],
        "reasoning": "简短说明判断依据"
    }}
    示例
    输入："PD-1抗体在肺癌治疗中的最新临床进展如何？"
    输出：
    json{{
        "intent_type": "qa_external",
        "confidence": 0.9,
        "entities": {{
            "target": "PD-1",
            "disease": "肺癌",
            "drug": "PD-1抗体",
            "therapy": "免疫治疗"
        }},
        "relevant_experts": ["clinical_expert", "literature_expert"],
        "reasoning": "用户询问特定的最新临床进展，需要查询外部临床试验数据"
    }}
    现在请分析用户输入并返回JSON结果：
    """
def get_memory_search_prompt(query: str, memory_context: str) -> str:
    """
    用于qa_internal类型的记忆检索提示词
    """
    return f"""
    基于以下已有的报告内容和对话历史，回答用户的问题。
    已有信息
    {memory_context}
    用户问题
    {query}
    要求

    直接基于已有信息回答，不要推测或添加新信息
    如果已有信息中没有相关内容，明确告知用户
    保持简洁、准确、相关

    回答：
    """

def get_expert_aggregation_prompt(expert_results: dict, intent_type: str, original_query: str) -> str:
    """
    整合多个专家结果的提示词
    """
    return f"""
    请整合以下专家分析结果，为用户提供统一的回答。
    用户原始问题
    {original_query}
    意图类型
    {intent_type}
    各专家分析结果
    {expert_results}
    整合要求
    {"根据意图类型：" if intent_type else ""}
    {
    "- 如果是report：整合成结构化的报告段落" if intent_type == "report" else
    "- 如果是qa_external：综合各专家信息给出准确答案" if intent_type == "qa_external" else
    "- 如果是target_comparison：整理成清晰的对比表格或列表" if intent_type == "target_comparison" else
    ""
    }
    请提供整合后的回答："""