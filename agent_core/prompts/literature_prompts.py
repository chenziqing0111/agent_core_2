# agent_core/prompts/literature_prompts.py

"""
文献分析相关提示词
"""


def get_disease_mechanism_prompt(gene: str, context: str, references: str) -> str:
    """疾病机制分析提示词"""
    return f"""你是资深医学专家，请基于以下文献信息深入分析基因 {gene} 的疾病机制。

相关文献段落：
{context}

{references}

请以如下结构输出：
### 疾病机制与临床需求分析（Gene: {gene}）

#### 1. 疾病关联谱
- **强关联疾病**：疾病名称 | 遗传模式 | 证据等级 [文献X]
- **中等关联疾病**：疾病名称 | OR值 | 证据来源 [文献X]

#### 2. 分子病理机制
- **正常生理功能**：蛋白功能和信号通路
- **致病机制**：功能丧失/获得型变异

#### 3. 临床需求评估
- **已有治疗**：药物和疗效
- **未满足需求**：治疗空白
- **机会识别**：新靶点和策略

注意：只基于提供的文献信息回答。"""


def get_treatment_strategy_prompt(gene: str, context: str, references: str) -> str:
    """治疗策略分析提示词"""
    return f"""你是临床医学专家，请基于以下文献信息分析基因 {gene} 相关的治疗策略。

相关文献段落：
{context}

{references}

请以如下结构输出：
### 治疗策略综合分析（Gene: {gene}）

#### 1. 治疗方法全景
- **已上市治疗**：药物 | 机制 | 临床数据 [文献X]
- **临床试验**：分期 | 初步结果 [文献X]

#### 2. 疗效与安全性
- **疗效对比**：ORR、PFS、OS
- **安全性**：不良反应

#### 3. 个体化治疗
- **生物标志物**：预测指标
- **联合治疗**：方案和证据

注意：严格基于文献证据。"""


def get_target_analysis_prompt(gene: str, context: str, references: str) -> str:
    """靶点分析提示词"""
    return f"""你是药物靶点研究专家，请基于以下文献信息分析基因 {gene} 的成药性。

相关文献段落：
{context}

{references}

请以如下结构输出：
### 靶点成药性分析（Gene: {gene}）

#### 1. 靶点可成药性
- **蛋白结构**：功能域和结合位点
- **化学可干预性**：小分子可行性

#### 2. 靶点验证
- **遗传学证据**：GWAS研究 [文献X]
- **药理学验证**：工具化合物 [文献X]

#### 3. 药物设计策略
- **先导化合物**：来源和优化
- **新技术**：AI/CRISPR应用

注意：基于文献证据。"""


def get_therapy_mechanism_prompt(therapy: str, disease: str, context: str, references: str) -> str:
    """治疗方式的机制分析提示词"""
    disease_str = disease if disease else "相关疾病"
    
    return f"""你是生物医学专家，请基于文献分析{therapy}治疗{disease_str}的作用机制。

相关文献：
{context}

{references}

请分析：
### {therapy}治疗机制分析

#### 1. 作用原理
- 分子机制
- 细胞水平效应
- 组织/器官影响

#### 2. 治疗靶点
- 直接靶点
- 间接作用
- 脱靶效应

#### 3. 临床应用
- 适应症
- 疗效证据
- 安全性

基于文献证据回答。"""


def get_therapy_strategy_prompt(therapy: str, context: str, references: str) -> str:
    """治疗方式的策略分析提示词"""
    return f"""分析{therapy}的治疗策略和临床应用。

相关文献：
{context}

{references}

请分析：
### {therapy}治疗策略

#### 1. 技术发展
- 技术演进
- 当前水平
- 技术挑战

#### 2. 临床转化
- 临床试验进展
- 已批准应用
- 在研项目

#### 3. 优化策略
- 疗效提升
- 安全性改善
- 给药优化

基于文献分析。"""


def get_therapy_target_prompt(therapy: str, context: str, references: str) -> str:
    """治疗方式的靶点分析提示词"""
    return f"""分析{therapy}的作用靶点和机制。

相关文献：
{context}

{references}

请分析：
### {therapy}靶点分析

#### 1. 主要靶点
- 直接靶点识别
- 靶点特异性
- 靶点验证

#### 2. 靶点调控
- 调控机制
- 效应评估
- 耐药机制

#### 3. 新靶点发现
- 潜在靶点
- 验证策略
- 开发前景

基于文献证据。"""


def get_combined_entity_prompt(entity_dict: dict, dimension: str, context: str, references: str) -> str:
    """组合实体的分析提示词"""
    
    # 构建实体描述
    entity_parts = []
    if entity_dict.get('disease'):
        entity_parts.append(f"疾病: {entity_dict['disease']}")
    if entity_dict.get('target'):
        entity_parts.append(f"靶点: {entity_dict['target']}")
    if entity_dict.get('therapy'):
        entity_parts.append(f"治疗: {entity_dict['therapy']}")
    if entity_dict.get('drug'):
        entity_parts.append(f"药物: {entity_dict['drug']}")
    
    entity_str = ", ".join(entity_parts)
    
    dimension_map = {
        'disease_mechanism': '疾病机制',
        'treatment_strategy': '治疗策略',
        'target_analysis': '靶点分析'
    }
    
    dim_name = dimension_map.get(dimension, dimension)
    
    return f"""基于以下文献信息，分析{entity_str}的{dim_name}。

相关文献：
{context}

{references}

请提供结构化的分析，包括：
1. 核心发现
2. 机制解析
3. 临床意义
4. 研究进展

注意：严格基于文献证据，标注引用来源。"""