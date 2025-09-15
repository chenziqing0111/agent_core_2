# agent_core/prompts/literature_prompts.py

"""
Literature Prompts - 文献分析提示词模块
负责：生成各种维度的分析提示词
优化版本：支持intent_type的输出格式控制
"""

from typing import Dict, Any, Optional, List


class LiteraturePrompts:
    """文献分析提示词生成器 - 支持intent_type的完整版"""
    
    def __init__(self):
        # 基础段落样式（所有intent共享）
        self.BASE_STYLE = """
请基于提供的文献内容进行专业分析。要求：
1. 分析必须基于提供的文献证据
2. 在陈述重要观点后立即标注引用[REF:PMID]
3. 保持客观和学术性
"""
        
        # Report模式的输出格式
        self.REPORT_FORMAT = """
输出格式要求（报告模式）：
1. 使用段落式写作，每个段落500-1000字
2. 段落之间有逻辑过渡
3. 包含概述、详细分析、结论三个部分
4. 每段至少包含2-5个文献引用
5. 语言正式、学术

结构示例：
【概述】
简要介绍研究背景和重要性...

【详细分析】
深入分析机制/临床应用/研究进展...

【结论】
总结关键发现和未来展望...
"""
        
        # QA模式的输出格式
        self.QA_FORMAT = """
输出格式要求（问答模式）：
1. 直接回答用户问题，不需要冗长的背景介绍
2. 第一句话就给出核心答案
3. 用2-3句话提供关键支持证据
4. 简洁明了，总长度不超过200字
5. 只引用最相关的1-2篇文献

回答模式：
[直接答案] + [关键证据] + [简短总结]
"""
        
        # Comparison模式的输出格式
        self.COMPARISON_FORMAT = """
输出格式要求（对比分析模式）：
1. 首先按照报告模式生成完整分析
2. 在分析基础上，对当前靶点/方案进行评估
3. 提供结构化的对比维度（如效果、安全性、成本等）
4. 给出综合评分建议（1-10分）

结构要求：
【标准分析报告】
（同报告模式）

【靶点/方案评估】
- 优势分析
- 劣势分析
- 与其他方案对比
- 综合评分：X/10分
- 评分理由
"""
        
        # 初始化16种组合的模板
        self.combination_templates = self._init_combination_templates()
    
    def get_combination_prompt(self, entity: Any, context: str, 
                              intent_type: str = 'report',
                              original_query: str = '') -> str:
        """
        根据实体组合和意图类型获取相应的prompt
        
        Args:
            entity: 实体对象
            context: RAG检索到的文献内容
            intent_type: 意图类型 (report/qa_external/target_comparison)
            original_query: 用户原始查询
        """
        # 生成组合键
        combo_key = self._get_combination_key(entity)
        
        # 构建prompt的各个部分
        prompt_parts = []
        
        # 1. 基础指令
        prompt_parts.append(self.BASE_STYLE)
        
        # 2. 实体相关的分析指令（根据组合选择）
        if combo_key in self.combination_templates:
            analysis_instruction = self.combination_templates[combo_key](entity)
        else:
            analysis_instruction = self._get_default_instruction(entity)
        prompt_parts.append(analysis_instruction)
        
        # 3. 添加文献上下文
        prompt_parts.append("\n## 相关文献内容：")
        prompt_parts.append(context)
        
        # 4. 根据intent_type添加输出格式要求
        prompt_parts.append("\n## 输出要求：")
        if intent_type == 'qa_external':
            prompt_parts.append(self.QA_FORMAT)
            if original_query:
                prompt_parts.append(f"\n用户问题：{original_query}")
                prompt_parts.append("请直接回答上述问题。")    
            elif intent_type == 'target_comparison':
                prompt_parts.append(self.REPORT_FORMAT)  # 使用report的段落格式
                prompt_parts.append(self.COMPARISON_FORMAT)  # 追加评分要求
        else:  # report
            prompt_parts.append(self.REPORT_FORMAT)
        
        # 5. 结尾强调
        prompt_parts.append("\n请基于以上要求生成分析内容。")
        
        return '\n'.join(prompt_parts)
    
    def _get_combination_key(self, entity: Any) -> str:
        """生成实体组合的键"""
        parts = []
        if getattr(entity, 'target', None): parts.append('T')
        if getattr(entity, 'disease', None): parts.append('D')
        if getattr(entity, 'therapy', None): parts.append('R')  # R for theRapy
        if getattr(entity, 'drug', None): parts.append('M')  # M for Medicine
        return ''.join(parts)
    
    def _init_combination_templates(self):
        """初始化16种组合模板的分析指令"""
        return {
            # ========== 单一实体（4种）==========
            'T': self._target_only_prompt,
            'D': self._disease_only_prompt,
            'R': self._therapy_only_prompt,
            'M': self._drug_only_prompt,
            
            # ========== 双实体组合（6种）==========
            'TD': self._target_disease_prompt,
            'TR': self._target_therapy_prompt,
            'TM': self._target_drug_prompt,
            'DR': self._disease_therapy_prompt,
            'DM': self._disease_drug_prompt,
            'RM': self._therapy_drug_prompt,
            
            # ========== 三实体组合（4种）==========
            'TDR': self._target_disease_therapy_prompt,
            'TDM': self._target_disease_drug_prompt,
            'TRM': self._target_therapy_drug_prompt,
            'DRM': self._disease_therapy_drug_prompt,
            
            # ========== 四实体组合（1种）==========
            'TDRM': self._all_entities_prompt,
            
            # ========== 空查询（1种）==========
            '': self._empty_prompt        
            }
    
    
    # ==================== 单一实体 Prompts ====================
    
    def _target_only_prompt(self, entity: Any, context: str) -> str:
        """仅靶点"""
        return f"""
你是药物靶点专家，请基于以下文献分析{entity.target}作为治疗靶点的潜力。


请用3个连贯的段落分析：

第一段介绍{entity.target}的基本功能和生物学重要性，包括但不限于其蛋白结构、表达分布、生理功能以及在关键生物学过程中的作用。说明该基因/蛋白的进化保守性和功能域特征[REF:PMID]。

第二段分析该靶点与人类疾病的关联，讨论遗传学证据、表达异常、功能改变在不同疾病中的作用。评估其作为治疗靶点的潜力，包括但不限于可药性、选择性窗口、安全性考虑[REF:PMID]。

第三段探讨针对该靶点的治疗开发策略和现状，包括但不限于但不限于小分子、抗体、基因治疗等不同方法的可行性。总结该靶点的开发价值和主要挑战[REF:PMID]。"""
    
    def _disease_only_prompt(self, entity: Any, context: str) -> str:
        """仅疾病"""
        return f"""
你是疾病研究专家，请基于以下文献分析{entity.disease}的治疗靶点和策略。


请用3个连贯的段落分析：

第一段概述{entity.disease}的临床特征、流行病学和疾病负担，说明其发病机制的关键环节和病理特征。讨论当前治疗面临的主要挑战和未满足的医疗需求[REF:PMID]。

第二段深入分析该疾病的分子机制和潜在治疗靶点，包括但不限于已验证的靶点和新发现的候选靶点。评估不同靶点的治疗潜力、开发可行性和临床转化前景[REF:PMID]。

第三段讨论当前和未来的治疗策略，包括但不限于药物治疗、基因治疗、细胞治疗等不同模式的应用。如有需要，请分析精准医疗和个体化治疗在该疾病中的机会[REF:PMID]。"""
    
    def _therapy_only_prompt(self, entity: Any, context: str) -> str:
        """仅治疗方式"""
        return f"""
你是治疗技术专家，请基于以下文献分析{entity.therapy}的应用和发展。


请用3个连贯的段落分析：

第一段介绍{entity.therapy}的基本原理、技术特点和作用机制，说明其相比传统治疗的优势和创新点。讨论该治疗方式的技术成熟度和临床应用现状[REF:PMID]。

第二段分析该治疗方式在不同疾病领域的应用，重点讨论成功案例和临床证据。评估其适应症范围、疗效特点和安全性profile[REF:PMID]。

第三段探讨该治疗技术的优化方向和未来发展，包括但不限于技术改进、新型载体、联合策略等。分析其在精准医疗时代的应用前景和潜在突破[REF:PMID]。"""
    
    def _drug_only_prompt(self, entity: Any, context: str) -> str:
        """仅药物"""
        return f"""
你是药物研究专家，请基于以下文献分析{entity.drug}的特性和应用。


请用3个连贯的段落分析：

第一段介绍{entity.drug}的药理学特征，包括但不限于作用机制、靶点、药代动力学和药效学特性。说明其化学结构或生物学特性如何决定其功能[REF:PMID]。

第二段分析该药物的临床应用和疗效证据，包括但不限于适应症、临床试验结果、真实世界数据。讨论其在治疗中的定位和与其他药物的比较优势[REF:PMID]。

第三段评估该药物的安全性、耐药性和优化策略，探讨新适应症开发、联合用药、个体化给药等发展方向[REF:PMID]。"""
    
    # ==================== 双实体组合 Prompts ====================
    
    def _target_disease_prompt(self, entity: Any, context: str) -> str:
        """靶点+疾病（最重要的组合）"""
        return f"""
你是精准医疗专家，请基于以下文献分析{entity.target}作为{entity.disease}治疗靶点的价值。


请用3个连贯的段落分析：

第一段阐述{entity.target}在{entity.disease}发病机制中的作用，包括但不限于遗传学证据、表达改变、功能异常、生物学通路等多层面证据。分析该靶点在疾病发生发展中是原因还是结果，评估其作为治疗靶点的因果关系强度[REF:PMID]。

第二段详细探讨靶向{entity.target}治疗{entity.disease}的策略和进展，包括但不限于小分子药物、抗体、基因治疗等不同方式的开发现状。分析临床前研究和临床试验的关键数据，评估疗效和安全性[REF:PMID]。

第三段讨论{entity.disease}疾病的其他治疗策略，比较该基因作为靶点治疗该疾病的优势[REF:PMID]。"""
    
    def _target_therapy_prompt(self, entity: Any, context: str) -> str:
        """靶点+治疗方式"""
        return f"""
你是治疗开发专家，请基于以下文献分析如何用{entity.therapy}方法靶向{entity.target}。


请用3个连贯的段落分析：

第一段分析{entity.target}相关疾病有哪些，分别在发病机制中的作用，包括但不限于遗传学证据、表达改变、功能异常、生物学通路等多层面证据。这些疾病传的传统治疗方式[REF:PMID]。

第二段分析{entity.target}的特性是否适合{entity.therapy}方法干预，讨论该靶点的结构、功能、表达特征如何影响治疗方式的选择。评估技术可行性和预期效果[REF:PMID]。

第三段详细介绍使用{entity.therapy}靶向{entity.target}的具体策略和研究进展，包括但不限于技术平台、递送系统、效果验证等。分析成功案例和失败教训[REF:PMID]。"""
    
    def _target_drug_prompt(self, entity: Any, context: str) -> str:
        """靶点+药物"""
        return f"""
你是药理学专家，请基于以下文献分析{entity.drug}与{entity.target}的相互作用。


请用3个连贯的段落分析：
第一段分析{entity.drug}的适应症有哪些，{entity.target}在主要适应症中的作用，包括但不限于遗传学证据、表达改变、功能异常、生物学通路等多层面证据。[REF:PMID]。

第二段详细描述{entity.drug}如何作用于{entity.target}，包括但不限于结合模式、作用机制、功能影响。分析药物-靶点相互作用的分子基础和选择性[REF:PMID]。

第三段评估{entity.drug}对{entity.target}的调节效果，包括但不限于体外活性、体内效果、临床疗效。讨论剂量-效应关系和治疗窗口[REF:PMID]。"""
    
    def _disease_therapy_prompt(self, entity: Any, context: str) -> str:
        """疾病+治疗方式"""
        return f"""
你是临床治疗专家，请基于以下文献分析{entity.therapy}在{entity.disease}治疗中的应用。


请用3个连贯的段落分析：

第一段分析{entity.therapy}治疗{entity.disease}的理论基础和作用机制，说明该治疗方式如何针对疾病的关键病理环节，如果存在请分析可能相关的基因靶点。讨论治疗原理和预期效果[REF:PMID]。

第二段详细评估临床应用证据，包括但不限于临床试验结果、真实世界数据、治疗指南推荐。分析疗效、安全性和患者获益[REF:PMID]。

第三段评估相比于{entity.disease}的其他治疗方式，{entity.therapy}的优劣势，如研究进展、应用广泛程度等[REF:PMID]。"""
    
    def _disease_drug_prompt(self, entity: Any, context: str) -> str:
        """疾病+药物"""
        return f"""
你是临床药理专家，请基于以下文献分析{entity.drug}治疗{entity.disease}的价值。


请用3个连贯的段落分析：

第一段介绍{entity.drug}治疗{entity.disease}的作用机制和理论基础，如果存在请分析可能相关的基因靶点。说明该药物如何改善疾病的病理生理过程。分析药物特性与疾病特征的匹配度[REF:PMID]。

第二段详细评估临床证据，包括但不限于关键临床试验、疗效数据、安全性信息。与其他药物或治疗方式相比，分析该药物的定位和优劣势[REF:PMID]。

第三段讨论临床应用策略，包括但不限于适用人群、用药时机、剂量优化、联合用药等。分析真实世界应用的挑战和解决方案[REF:PMID]。"""
    
    def _therapy_drug_prompt(self, entity: Any, context: str) -> str:
        """治疗方式+药物"""
        return f"""
你是药物开发专家，请基于以下文献分析{entity.drug}作为{entity.therapy}类药物的特点。


请用3个连贯的段落分析：

第一段介绍{entity.drug}的适应症，如果存在请分析相关联的基因靶点。该药物{entity.therapy}类别中的定位，分析其技术特点、作用机制与该治疗方式的关系。说明其代表性和创新性[REF:PMID]。

第二段比较在{entity.drug}适应症中，其与其他{entity.therapy}类药物，分析优势、劣势和差异化特征。评估其竞争力和市场定位[REF:PMID]。

第三段探讨{entity.drug}推动{entity.therapy}领域发展的意义，包括但不限于技术突破、适应症拓展、联合策略等。展望该类药物的发展趋势[REF:PMID]。"""
    
    # ==================== 三实体组合 Prompts ====================
    
    def _target_disease_therapy_prompt(self, entity: Any, context: str) -> str:
        """靶点+疾病+治疗方式"""
        return f"""
你是转化医学专家，请分析使用{entity.therapy}方法靶向{entity.target}治疗{entity.disease}的策略。


请用3个连贯的段落分析：

第一段详细分析{entity.target}在{entity.disease}中的作用机制，以及{entity.therapy}方法干预该靶点的科学依据。评估这种组合的理论可行性和预期效果[REF:PMID]。

第二段讨论使用{entity.therapy}靶向{entity.target}治疗{entity.disease}的研究进展和临床开发现状。分析关键技术挑战和解决方案[REF:PMID]。

第三段评估相比于{entity.disease}的其他治疗方式，针对{entity.target}进行{entity.therapy}治疗的优劣势。"""
    
    def _target_disease_drug_prompt(self, entity: Any, context: str) -> str:
        """靶点+疾病+药物"""
        return f"""
你是精准药物专家，请分析{entity.drug}通过作用于{entity.target}治疗{entity.disease}的机制和效果。


请用3个连贯的段落分析：

第一段详细阐述{entity.drug}如何通过调节{entity.target}来改善{entity.disease}，包括但不限于分子机制、信号通路、病理改善等多层面分析[REF:PMID]。

第二段评估该药物-靶点-疾病组合的临床证据，包括但不限于生物标志物验证、疗效数据、患者分层策略。分析治疗响应的预测因素[REF:PMID]。

第三段评估相比于{entity.disease}的其他治疗方式，针对{entity.target}使用{entity.drug}治疗的优劣势[REF:PMID]。"""
    
    def _target_therapy_drug_prompt(self, entity: Any, context: str) -> str:
        """靶点+治疗方式+药物"""
        return f"""
你是创新药物专家，请分析{entity.drug}作为{entity.therapy}类药物靶向{entity.target}的特点和价值。


请用3个连贯的段落分析：

第一段分析{entity.drug}的适应症，其在适应症中的作用机制[REF:PMID]。

第二段分析{entity.target}与该适应症的关联，包括但不限于遗传学证据、表达改变、功能异常、生物学通路等多层面证据[REF:PMID]。

第三段评估如何利用{entity.therapy}技术特点来有效靶向{entity.target}，讨论药物设计理念和技术创新[REF:PMID]。

第四段评估该药物相比其他靶向{entity.target}的{entity.therapy}类药物的优势，分析差异化特征和临床价值[REF:PMID]。"""
    
    
    def _disease_therapy_drug_prompt(self, entity: Any, context: str) -> str:
        """疾病+治疗方式+药物"""
        return f"""
你是临床治疗专家，请分析{entity.drug}作为{entity.therapy}方案在{entity.disease}治疗中的应用。


请用3个连贯的段落分析：

第一段介绍{entity.drug}在{entity.disease}的{entity.therapy}治疗体系中的定位，分析其作用机制如何契合疾病特点和治疗理念[REF:PMID]。

第二段详细评估临床应用效果，包括但不限于与其他{entity.therapy}方案的比较、在{entity.disease}不同阶段的应用、真实世界疗效[REF:PMID]。

第三段探讨优化应用策略，包括但不限于精准选择患者、个体化方案、联合治疗等，展望该治疗模式的发展前景[REF:PMID]。"""
    
    # ==================== 四实体组合 Prompt ====================
    
    def _all_entities_prompt(self, entity: Any, context: str) -> str:
        """靶点+疾病+治疗方式+药物（全组合）"""
        return f"""
你是综合医学专家，请分析{entity.drug}作为{entity.therapy}类药物通过靶向{entity.target}治疗{entity.disease}的完整图景。


请用3-4个连贯的段落综合分析：

第一段阐述核心治疗逻辑：{entity.drug}如何体现{entity.therapy}的技术特点，通过作用于{entity.target}来治疗{entity.disease}。分析这个完整治疗链条的科学基础[REF:PMID]。

第二段评估临床价值和证据：该药物在{entity.disease}患者中的疗效、{entity.target}作为生物标志物的价值、{entity.therapy}方法的优势体现。提供关键临床数据支持[REF:PMID]。

第三段分析竞争优势和定位：与其他靶向{entity.target}的药物比较、在{entity.disease}的{entity.therapy}治疗中的地位、精准医疗应用价值[REF:PMID]。

第四段展望未来发展：优化方向、联合策略、该模式对精准医疗的启示。提出改进建议和研究方向[REF:PMID]。"""
    
    # ==================== 空查询 Prompt ====================
    
    def _empty_prompt(self, entity: Any, context: str) -> str:
        """无实体查询"""
        return f"""
请基于提供的文献内容进行分析。


请提供相关的科学见解和分析。"""
    
    def _get_default_instruction(self, entity: Any) -> str:
        """默认指令（兜底）"""
        parts = []
        if getattr(entity, 'target', None):
            parts.append(f"靶点{entity.target}")
        if getattr(entity, 'disease', None):
            parts.append(f"疾病{entity.disease}")
        if getattr(entity, 'therapy', None):
            parts.append(f"治疗{entity.therapy}")
        if getattr(entity, 'drug', None):
            parts.append(f"药物{entity.drug}")
        
        focus = "、".join(parts) if parts else "相关内容"
        
        return f"""
## 分析任务：{focus}的文献分析

请基于提供的文献，分析以下方面：
1. 基本概念和背景
2. 作用机制和原理
3. 研究进展和发现
4. 临床应用和意义
5. 问题和展望
"""

    # ==================== 特殊格式生成方法 ====================
    
    def get_qa_prompt(self, question: str, context: str, entity: Any = None) -> str:
        """
        生成QA专用prompt
        
        Args:
            question: 用户问题
            context: 文献上下文
            entity: 实体对象（可选）
        """
        prompt = f"""
{self.BASE_STYLE}

## 用户问题：
{question}

## 相关文献内容：
{context}

{self.QA_FORMAT}

请直接、准确、简洁地回答用户问题。
"""
        return prompt
    
    def get_comparison_prompt(self, entities_list: List[Any], context: str) -> str:
        """
        生成对比分析专用prompt
        
        Args:
            entities_list: 要对比的实体列表
            context: 文献上下文
        """
        # 提取所有靶点进行对比
        targets = []
        for entity in entities_list:
            if getattr(entity, 'target', None):
                targets.append(entity.target)
        
        prompt = f"""
{self.BASE_STYLE}

## 对比分析任务：
对比以下靶点/方案：{', '.join(targets)}

## 相关文献内容：
{context}

{self.COMPARISON_FORMAT}

请提供结构化的对比分析和评分。
"""
        return prompt