# agent_core/prompts/literature_prompts.py

"""
Literature Prompts - 文献分析提示词模块
负责：生成各种维度的分析提示词
"""

from typing import Dict, Any, Optional


class LiteraturePrompts:
    """文献分析提示词生成器"""
    
    def __init__(self):
        # 维度特定的提示词模板
        self.dimension_templates = self._init_dimension_templates()
        
        # 通用模板
        self.general_template = self._init_general_template()
    
    def get_dimension_prompt(self, entity: Any, dimension_key: str, 
                            dimension_question: str, context: str) -> str:
        """
        获取维度特定的提示词
        
        Args:
            entity: 实体对象
            dimension_key: 维度键
            dimension_question: 维度问题
            context: 格式化的上下文
            
        Returns:
            完整的提示词
        """
        # 尝试获取特定模板
        if dimension_key in self.dimension_templates:
            return self.dimension_templates[dimension_key](entity, context)
        
        # 使用通用模板
        return self.general_template(entity, dimension_question, context)
    
    def _init_dimension_templates(self) -> Dict:
        """初始化维度特定的提示词模板"""
        return {
            'gene_disease_association': self._gene_disease_association_prompt,
            'gene_mechanism': self._gene_mechanism_prompt,
            'gene_druggability': self._gene_druggability_prompt,
            'disease_pathogenesis': self._disease_pathogenesis_prompt,
            'disease_treatment_landscape': self._disease_treatment_landscape_prompt,
            'disease_targets': self._disease_targets_prompt,
            'gene_disease_mechanism': self._gene_disease_mechanism_prompt,
            'gene_disease_therapy': self._gene_disease_therapy_prompt,
            'gene_disease_biomarker': self._gene_disease_biomarker_prompt,
            'therapy_mechanism': self._therapy_mechanism_prompt,
            'therapy_efficacy': self._therapy_efficacy_prompt,
            'therapy_applications': self._therapy_applications_prompt,
            'drug_mechanism': self._drug_mechanism_prompt,
            'drug_clinical': self._drug_clinical_prompt,
            'drug_market': self._drug_market_prompt
        }
    
    def _init_general_template(self):
        """初始化通用模板"""
        def template(entity: Any, question: str, context: str) -> str:
            entity_desc = self._format_entity(entity)
            
            return f"""你是资深生物医学专家，请基于以下文献信息回答问题。

研究对象：{entity_desc}
研究问题：{question}

相关文献内容：
{context}

请提供结构化的分析，包括：
1. 核心发现与结论
2. 支持证据的强度
3. 研究空白和局限性
4. 临床或研究意义
5. 未来研究方向建议

要求：
- 严格基于提供的文献证据
- 标注引用来源 [REF]
- 避免过度推测
- 保持客观专业

请用中文回答。"""
        
        return template
    
    # ========== 基因相关提示词 ==========
    
    def _gene_disease_association_prompt(self, entity: Any, context: str) -> str:
        """基因-疾病关联分析提示词"""
        return f"""你是遗传学专家，请基于以下文献分析{entity.target}基因与疾病的关联性。

相关文献内容：
{context}

请按以下结构分析：

## 1. 疾病关联谱
- 强关联疾病（OR>2或P<0.001）
- 中等关联疾病（OR 1.5-2或P<0.01）
- 弱关联疾病（OR 1.2-1.5或P<0.05）

## 2. 分子机制
- 正常生理功能
- 致病机制（功能丧失/获得）
- 信号通路影响

## 3. 临床意义
- 诊断价值
- 预后评估
- 治疗指导

## 4. 证据质量评估
- 研究数量和质量
- 证据一致性
- 研究局限性

请基于文献证据，用中文详细分析。标注引用[REF]。"""
    
    def _gene_mechanism_prompt(self, entity: Any, context: str) -> str:
        """基因分子机制提示词"""
        return f"""你是分子生物学专家，请基于以下文献分析{entity.target}基因的分子机制。

相关文献内容：
{context}

请按以下结构分析：

## 1. 基因功能概述
- 编码蛋白特征
- 亚细胞定位
- 组织表达谱

## 2. 分子功能
- 酶活性/结合特性
- 蛋白相互作用
- 转录调控

## 3. 信号通路
- 上游调控因子
- 下游效应分子
- 通路串扰

## 4. 生理作用
- 正常生理功能
- 发育过程作用
- 代谢调节

## 5. 调控机制
- 转录调控
- 翻译后修饰
- 表观遗传调控

请基于文献深入分析，标注引用[REF]。"""
    
    def _gene_druggability_prompt(self, entity: Any, context: str) -> str:
        """基因成药性评估提示词"""
        return f"""你是药物研发专家，请基于以下文献评估{entity.target}基因的成药性。

相关文献内容：
{context}

请按以下结构分析：

## 1. 靶点可成药性评估
- 蛋白结构特征（结合口袋、活性位点）
- 化学可干预性
- 选择性可能性

## 2. 靶点验证
- 遗传学证据（GWAS、敲除/敲减）
- 药理学验证（工具化合物）
- 疾病相关性强度

## 3. 药物开发策略
- 小分子抑制剂
- 抗体药物
- 基因治疗
- 其他新型疗法

## 4. 现有药物/在研管线
- 已上市药物
- 临床试验阶段药物
- 临床前研究


请提供专业的成药性分析，标注引用[REF]。"""
    
    # ========== 疾病相关提示词 ==========
    
    def _disease_pathogenesis_prompt(self, entity: Any, context: str) -> str:
        """疾病发病机制提示词"""
        return f"""你是病理学专家，请基于以下文献分析{entity.disease}的发病机制。

相关文献内容：
{context}

请按以下结构分析：

## 1. 疾病概述
- 定义和分类
- 流行病学特征
- 临床表现

## 2. 病因学
- 遗传因素
- 环境因素
- 诱发因素

## 3. 发病机制
- 分子病理基础
- 细胞病理改变
- 组织器官损伤

## 4. 病理生理
- 功能障碍
- 代偿机制
- 并发症发生

## 5. 疾病进展
- 自然病程
- 关键节点
- 预后因素

请深入分析病理机制，标注引用[REF]。"""
    
    def _disease_treatment_landscape_prompt(self, entity: Any, context: str) -> str:
        """疾病治疗现状提示词"""
        return f"""你是临床医学专家，请基于以下文献分析{entity.disease}的治疗现状。

相关文献内容：
{context}

请按以下结构分析：

## 1. 治疗指南和共识
- 国际指南推荐
- 一线治疗方案
- 二线及挽救治疗

## 2. 药物治疗
- 主要治疗药物
- 作用机制
- 疗效和安全性

## 3. 非药物治疗
- 手术治疗
- 放射治疗
- 物理治疗
- 生活方式干预

## 4. 新兴治疗
- 免疫治疗
- 靶向治疗
- 基因治疗
- 细胞治疗

## 5. 治疗挑战
- 耐药问题
- 不良反应
- 个体化治疗

请综合分析治疗现状，标注引用[REF]。"""
    
    def _disease_targets_prompt(self, entity: Any, context: str) -> str:
        """疾病治疗靶点提示词"""
        return f"""你是转化医学专家，请基于以下文献分析{entity.disease}的潜在治疗靶点。

相关文献内容：
{context}

请按以下结构分析：

## 1. 已验证靶点
- 临床验证靶点（已有药物）
- 作用机制
- 临床效果

## 2. 新兴靶点
- 临床前验证靶点
- 验证证据强度
- 开发阶段

## 3. 潜在靶点
- 基于组学发现的靶点
- 基于AI预测的靶点
- 验证需求

## 4. 靶点优先级
- 成药性评分
- 疾病相关性
- 技术可行性

## 5. 开发策略
- 针对不同靶点的策略
- 联合靶向方案
- 精准医疗应用

请提供全面的靶点分析，标注引用[REF]。"""
    
    # ========== 基因-疾病组合提示词 ==========
    
    def _gene_disease_mechanism_prompt(self, entity: Any, context: str) -> str:
        """基因在疾病中的作用机制提示词"""
        return f"""你是疾病机制研究专家，请基于以下文献分析{entity.target}在{entity.disease}发病中的作用。

相关文献内容：
{context}

请按以下结构分析：

## 1. 基因功能背景
- {entity.target}正常功能
- 在相关组织/细胞中的表达

## 2. 致病机制
- 基因变异类型和频率
- 功能改变（丧失/获得/显性负效应）
- 下游分子事件

## 3. 疾病表型关联
- 基因型-表型相关性
- 疾病严重程度
- 临床异质性

## 4. 信号通路影响
- 关键通路改变
- 网络效应
- 代偿机制

## 5. 治疗意义
- 作为治疗靶点的潜力
- 精准医疗应用
- 预后评估价值

请深入分析机制关联，标注引用[REF]。"""
    
    def _gene_disease_therapy_prompt(self, entity: Any, context: str) -> str:
        """基因靶向治疗策略提示词"""
        return f"""你是精准医疗专家，请基于以下文献分析针对{entity.target}治疗{entity.disease}的策略。

相关文献内容：
{context}

请按以下结构分析：

## 1. 靶点治疗理论基础
- 靶点验证证据
- 治疗窗口

## 2. 现有治疗方法
- 已批准药物
- 临床试验药物
- 疗效数据

## 3. 在研治疗策略
- 小分子抑制剂
- 单克隆抗体
- 基因治疗
- RNA疗法
- 其他

## 4. 耐药和应对
- 耐药机制
- 克服策略
- 生物标志物监测

请提供循证的治疗策略分析，标注引用[REF]。"""
    
    def _gene_disease_biomarker_prompt(self, entity: Any, context: str) -> str:
        """生物标志物价值提示词"""
        return f"""你是生物标志物研究专家，请基于以下文献评估{entity.target}作为{entity.disease}治疗靶点的价值。

相关文献内容：
{context}

请按以下结构分析：

## 1. 该疾病其他潜在治疗靶点

## 2. 该靶点相对于其他靶点的优势

## 3. 该靶点治疗该疾病的治疗方式选择及优势
- 小分子抑制剂
- 单克隆抗体
- 基因治疗
- RNA疗法
- 其他

请全面评估靶点治疗价值，标注引用[REF]。"""
    
    # ========== 治疗方式相关提示词 ==========
    
    def _therapy_mechanism_prompt(self, entity: Any, context: str) -> str:
        """治疗机制分析提示词"""
        disease_str = f"治疗{entity.disease}" if entity.disease else ""
        
        return f"""你是治疗机制研究专家，请基于以下文献分析{entity.therapy}{disease_str}的作用机制。

相关文献内容：
{context}

请按以下结构分析：

## 1. 治疗原理
- 基本作用机制
- 分子靶点
- 细胞效应

## 2. 药理学特征
- 药代动力学
- 药效动力学
- 剂量-效应关系

## 3. 生物学效应
- 直接效应
- 间接效应
- 系统性影响

## 4. 临床转化
- 从机制到疗效
- 生物标志物
- 个体差异

## 5. 优化策略
- 增效策略
- 减毒策略
- 联合方案

请深入分析治疗机制，标注引用[REF]。"""
    
    def _therapy_efficacy_prompt(self, entity: Any, context: str) -> str:
        """疗效与安全性提示词"""
        disease_str = f"治疗{entity.disease}" if entity.disease else ""
        
        return f"""你是循证医学专家，请基于以下文献评估{entity.therapy}{disease_str}的疗效和安全性。

相关文献内容：
{context}

请按以下结构分析：

## 1. 临床疗效
- 主要终点（ORR、PFS、OS）
- 次要终点
- 亚组分析

## 2. 真实世界数据
- 有效率
- 生存获益
- 生活质量改善

## 3. 安全性评估
- 常见不良反应
- 严重不良事件
- 长期安全性

## 4. 对比分析
- 与标准治疗对比
- 与同类治疗对比
- 成本效益分析

## 5. 适用人群
- 最佳获益人群
- 禁忌症
- 特殊人群考虑

请提供全面的疗效安全性评估，标注引用[REF]。"""
    
    def _therapy_applications_prompt(self, entity: Any, context: str) -> str:
        """治疗应用范围提示词"""
        return f"""你是临床应用专家，请基于以下文献分析{entity.therapy}的应用范围和前景。

相关文献内容：
{context}

请按以下结构分析：

## 1. 已批准适应症
- 适应症列表
- 批准依据
- 临床定位

## 2. 在研适应症
- 临床试验进展
- 初步结果
- 潜力评估

## 3. 潜在应用
- 机制支持的应用
- 探索性研究
- 跨病种应用

## 4. 应用优势
- 独特优势
- 适用场景
- 患者获益

## 5. 发展前景
- 技术改进方向
- 市场潜力
- 挑战和机遇

请综合分析应用前景，标注引用[REF]。"""
    
    # ========== 药物相关提示词 ==========
    
    def _drug_mechanism_prompt(self, entity: Any, context: str) -> str:
        """药物作用机制提示词"""
        return f"""你是药理学专家，请基于以下文献分析{entity.drug}的作用机制。

相关文献内容：
{context}

请按以下结构分析：

## 1. 分子机制
- 作用靶点
- 结合方式
- 抑制/激活类型

## 2. 药理作用
- 直接作用
- 下游效应
- 脱靶效应

## 3. 药代动力学
- 吸收分布
- 代谢转化
- 排泄途径

## 4. 药效关系
- 剂量依赖性
- 时间依赖性
- 个体差异

## 5. 耐药机制
- 已知耐药机制
- 克服策略
- 监测方法

请详细分析药物机制，标注引用[REF]。"""
    
    def _drug_clinical_prompt(self, entity: Any, context: str) -> str:
        """药物临床研究提示词"""
        return f"""你是临床研究专家，请基于以下文献分析{entity.drug}的临床研究进展。

相关文献内容：
{context}

请按以下结构分析：

## 1. 临床试验概况
- 各期试验数量
- 主要研究机构
- 患者入组情况

## 2. 关键试验结果
- III期试验结果
- 主要终点达成
- 安全性数据

## 3. 适应症开发
- 已批准适应症
- 在研适应症
- 扩展潜力

## 4. 特殊人群
- 儿童用药
- 老年人用药
- 肝肾功能不全

## 5. 上市后研究
- 真实世界证据
- 安全性监测
- 药物经济学

请全面分析临床进展，标注引用[REF]。"""
    
    def _drug_market_prompt(self, entity: Any, context: str) -> str:
        """药物市场分析提示词"""
        return f"""你是医药市场分析师，请基于以下文献分析{entity.drug}的市场情况。

相关文献内容：
{context}

请按以下结构分析：

## 1. 适应症覆盖
- 获批适应症
- 标签外使用
- 指南推荐

## 2. 临床定位
- 一线/二线治疗
- 联合用药地位
- 特殊人群应用

## 3. 竞争格局
- 同类药物比较
- 竞争优势
- 市场份额

## 4. 可及性
- 医保覆盖
- 价格策略
- 患者负担

## 5. 发展趋势
- 新适应症开发
- 剂型改进
- 市场前景

请提供市场分析洞察，标注引用[REF]。"""
    
    # ========== 辅助方法 ==========
    
    def _format_entity(self, entity: Any) -> str:
        """格式化实体描述"""
        parts = []
        
        if entity.target:
            parts.append(f"基因/靶点: {entity.target}")
        if entity.disease:
            parts.append(f"疾病: {entity.disease}")
        if entity.therapy:
            parts.append(f"治疗方式: {entity.therapy}")
        if entity.drug:
            parts.append(f"药物: {entity.drug}")
        
        return " | ".join(parts) if parts else "未指定"
    
    def get_summary_prompt(self, entity: Any, analysis_results: Dict, 
                          article_count: int) -> str:
        """生成执行摘要的提示词"""
        entity_desc = self._format_entity(entity)
        
        # 构建分析维度摘要
        dimension_summary = []
        for dim_key, result in analysis_results.items():
            if result.get('content'):
                dimension_summary.append(f"- {dim_key}: 已完成分析")
        
        dimensions_text = "\n".join(dimension_summary)
        
        return f"""基于以下文献分析结果，生成执行摘要。

研究对象：{entity_desc}
文献数量：{article_count}篇
完成的分析维度：
{dimensions_text}

请生成200字左右的执行摘要，包括：
1. 研究现状总结
2. 关键发现（2-3个要点）
3. 临床/研究意义
4. 建议和展望

要求简洁、准确、有洞察力。"""
    
    def get_report_section_prompt(self, section_type: str, content: Dict) -> str:
        """生成报告章节的提示词"""
        prompts = {
            'introduction': """基于提供的信息，生成报告引言部分，包括研究背景、目的和意义。""",
            'methodology': """描述文献检索和分析方法，包括数据来源、检索策略和分析框架。""",
            'results': """整理和呈现主要分析结果，使用适当的标题和结构。""",
            'discussion': """讨论主要发现的意义、局限性和未来研究方向。""",
            'conclusion': """总结关键发现和主要结论，提出建议。"""
        }
        
        return prompts.get(section_type, "生成报告内容。")