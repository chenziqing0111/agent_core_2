# 生物医学研究Agent系统 - README

## 项目概述
一个基于多Agent架构的生物医学研究分析系统，能够理解用户意图，调度专家Agent，生成研究报告。

## 当前进展状态 ✅

### 已完成模块
1. **Control Agent** ✅
   - 意图识别（4种类型）
   - 实体提取
   - 专家调度
   - 结果整合
   - 缓存机制
   - 记忆管理

2. **State Machine** ✅
   - 工作流定义
   - 流程编排
   - 路由决策
   - 执行管理

3. **Prompt系统** ✅
   - 意图解析prompt
   - 记忆搜索prompt
   - 结果整合prompt

4. **Literature Expert** ✅ (2024-12 完成优化)
   - 16种实体组合支持
   - 3维度查询策略
   - RAG优化（400词块大小）
   - 完整参数接收
   - 多格式输出支持

### 核心数据流
```python
用户输入 → Control Agent → State Machine → 专家Agent → 结果整合 → 响应
```

## 系统架构

### 意图类型定义
```python
class IntentType(Enum):
    REPORT = "report"              # 完整调研报告
    QA_EXTERNAL = "qa_external"    # 需要外部数据的问题
    QA_INTERNAL = "qa_internal"    # 基于历史对话的问题
    TARGET_COMPARISON = "target_comparison"  # 靶点/方案对比
```

### 实体类型
```python
@dataclass
class Entity:
    target: Optional[str] = None    # 基因/靶点
    disease: Optional[str] = None   # 疾病
    drug: Optional[str] = None      # 药物
    therapy: Optional[str] = None   # 治疗方式
```

### 专家Agent列表
- `literature_expert` ✅ - 文献调研（已完成优化）
- `clinical_expert` 📝 - 临床试验（待实现）
- `patent_expert` 📝 - 专利分析（待实现）
- `market_expert` 📝 - 市场分析（待实现）
- `editor_expert` ✅ - 报告生成（已完成）

## Literature Expert 优化完成 ✅

### 实现的改动

#### A. 参数接收优化
```python
async def analyze(self, 
                 params: Optional[Union[Dict[str, Any], Any]] = None,
                 # 保留旧参数以确保向后兼容
                 entity: Optional[Any] = None,
                 search_terms: Optional[List[str]] = None,
                 focus: Optional[str] = None,
                 **kwargs) -> Dict[str, Any]:
    """
    支持新旧两种调用方式
    新方式: params = {"intent_type": "...", "original_query": "...", "entities": {...}}
    旧方式: 直接传入entity, search_terms, focus
    """
```

#### B. 16种实体组合的3维度查询
```python
# TD组合示例
'TD': {
    'dimensions': ['association', 'mechanism', 'therapeutic_potential'],
    'queries': {
        'association': 'PD-1 lung cancer association genetic GWAS',
        'mechanism': 'PD-1 lung cancer pathway mechanism',
        'therapeutic_potential': 'PD-1 lung cancer treatment potential'
    }
}
```

#### C. 模块职责分离
- `literature_expert.py`: 流程控制和报告生成
- `literature_query_builder.py`: 查询构建逻辑
- `literature_rag.py`: 纯RAG功能
- `literature_prompts.py`: Prompt模板管理

#### D. 返回格式标准化
```python
# 轻量级返回格式，适配Control Agent的Memory
{
    "content": str,           # 主要内容
    "summary": str,          # 简短摘要
    "intent_type": str,      # 意图类型
    "entity_used": dict,     # 使用的实体
    "paper_count": int,      # 文献数量
    "chunks_used": int,      # 使用的文本块数
    "confidence": float,     # 置信度
    "key_references": list,  # 关键引用(最多5篇)
    "references": list,      # 完整参考文献列表
    
    # QA模式特有
    "direct_answer": str,    # 直接答案
    "evidence_strength": str,
    
    # Comparison模式特有
    "target_score": dict,    # 靶点评分
    "score_reasoning": str   # 评分理由
}
```

### 性能指标
- 检索100篇文献：~2秒
- RAG处理：~3秒
- 报告生成：~5-10秒
- 置信度：0.95（100篇文献时）

## 下一步开发计划 🚀

### 1. Clinical Expert 实现
基于Literature Expert的模式，实现：
- [ ] 接收完整entities参数
- [ ] ClinicalTrials.gov API集成
- [ ] 根据disease+drug精确查询
- [ ] intent_type适配（report/qa/comparison）
- [ ] 试验阶段和状态筛选

### 2. Patent Expert 实现
- [ ] 专利数据库API接入
- [ ] target+drug组合查询
- [ ] 专利布局分析（report模式）
- [ ] 技术趋势分析

### 3. Market Expert 实现
- [ ] 市场数据源集成
- [ ] disease流行病学数据
- [ ] drug竞品分析
- [ ] 市场规模预测

### 4. 系统级优化
- [ ] 多Expert并行调用优化
- [ ] 结果去重和融合策略
- [ ] 统一的错误处理机制
- [ ] API限流和重试策略

## 文件结构
```
agent_core/
├── agents/
│   ├── control_agent.py ✅
│   └── specialists/
│       ├── literature_expert.py ✅ 
│       ├── clinical_expert.py 📝
│       ├── patent_expert.py 📝
│       ├── market_expert.py 📝
│       └── editor_expert.py ✅
├── tools/
│   ├── retrievers/
│   │   └── pubmed_retriever.py ✅
│   └── rag/
│       ├── literature_rag.py ✅
│       └── literature_query_builder.py ✅
├── prompts/
│   ├── control_prompts.py ✅
│   └── literature_prompts.py ✅
├── state_machine/
│   ├── graph_definition.py ✅
│   └── graph_runner.py ✅
└── clients/
    └── llm_client.py ✅
```

## 测试状态

### 已通过测试 ✅
- Control Agent意图识别
- State Machine工作流
- 缓存机制（4312倍加速）
- Literature Expert完整功能
  - TD组合3维度查询
  - 100篇文献处理
  - 中文报告生成
  - 引用管理系统

### 待测试项目
- [ ] 其他实体组合（T/D/R/M/TDR/TDRM等）
- [ ] QA_EXTERNAL模式的简洁回答
- [ ] TARGET_COMPARISON的对比分析
- [ ] 多Expert结果融合

## 使用示例

### 基础调用
```python
from agent_core.state_machine.graph_runner import process_query

# 简单查询
result = await process_query("帮我分析PD-1在肺癌中的应用")

# 结果包含
{
    "success": True,
    "intent": {
        "type": "report",
        "entities": {"target": "PD-1", "disease": "肺癌"}
    },
    "response": {
        "type": "report",
        "html_content": "...",  # 完整报告
        "summary": "..."
    }
}
```

### Literature Expert直接调用
```python
from agent_core.agents.specialists.literature_expert import LiteratureExpert

expert = LiteratureExpert()
result = await expert.analyze({
    "intent_type": "report",
    "original_query": "PD-1肺癌研究",
    "entities": {
        "target": "PD-1",
        "disease": "lung cancer"
    }
})
```

## 依赖安装
```bash
# 核心依赖
pip install sentence-transformers faiss-cpu biopython
pip install openai numpy pandas

# 可选依赖
pip install nest-asyncio  # Jupyter支持
```

## 环境变量配置
```bash
# LLM配置
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=your_api_base  # 可选

# PubMed配置
PUBMED_EMAIL=your_email  # 推荐设置
```

## 更新日志

### v2.1.0 (2024-12-current)
- ✅ Literature Expert完整重构
- ✅ 16种实体组合支持
- ✅ RAG系统优化（chunk_size: 400词）
- ✅ 查询构建独立模块化
- ✅ 支持中英文混合处理

### v2.0.0 (2024-12)
- ✅ Control Agent实现
- ✅ State Machine工作流
- ✅ 基础Expert框架

### v1.0.0
- 初始版本

## 贡献指南

欢迎贡献代码！优先实现：
1. Clinical Expert
2. Patent Expert  
3. Market Expert

请遵循现有的代码结构和命名规范。

## License
MIT

## 联系方式
如有问题或建议，请提交Issue。