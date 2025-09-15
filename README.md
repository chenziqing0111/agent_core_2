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
- `literature_expert` - 文献调研
- `clinical_expert` - 临床试验
- `patent_expert` - 专利分析  
- `market_expert` - 市场分析
- `editor_expert` - 报告生成（仅用于report类型）

## 下一步优化计划 🚀

### 子Expert优化方向

#### 当前问题
- 子Expert目前只接收`target`参数
- 没有利用完整的entity信息
- 没有根据intent_type调整返回格式
- 没有使用original_query进行针对性回答

#### 需要优化的内容

1. **参数注入标准化**
```python
# 所有子Expert应该接收的标准参数
expert_params = {
    "intent_type": "report/qa_external/target_comparison",
    "original_query": "用户原始问题",
    "entities": {
        "target": "PD-1",
        "disease": "肺癌", 
        "drug": "帕博利珠单抗",
        "therapy": "免疫治疗"
    }
}
```

2. **根据intent_type调整行为**
```python
class SubExpert:
    async def analyze(self, params: Dict):
        intent_type = params['intent_type']
        
        if intent_type == 'report':
            # 返回详细的报告段落
            return self.generate_detailed_section()
        elif intent_type == 'qa_external':
            # 返回针对性的简短答案
            return self.answer_specific_question()
        elif intent_type == 'target_comparison':
            # 返回对比数据
            return self.generate_comparison_data()
```

3. **优化检索策略**
```python
# 利用所有entity字段构建更精确的查询
def build_search_query(entities):
    query_parts = []
    if entities.get('target'):
        query_parts.append(entities['target'])
    if entities.get('disease'):
        query_parts.append(f"AND {entities['disease']}")
    if entities.get('drug'):
        query_parts.append(f"OR {entities['drug']}")
    # ...组合查询
```

4. **统一返回格式**
```python
# Report模式返回
{
    "title": "章节标题",
    "summary": "摘要",
    "key_findings": [...],
    "detailed_content": "...",
    "references": [...]
}

# QA模式返回
{
    "answer": "直接回答",
    "evidence": "支持证据",
    "confidence": 0.85,
    "sources": [...]
}

# Comparison模式返回
{
    "comparison_table": {...},
    "advantages": {...},
    "disadvantages": {...},
    "recommendation": "..."
}
```

### 各Expert具体优化任务

#### 1. Literature Expert
- [ ] 接收完整entities参数
- [ ] 根据disease筛选相关文献
- [ ] 根据intent_type调整返回详细度
- [ ] 使用original_query优化相关性排序

#### 2. Clinical Expert  
- [ ] 利用disease和drug字段精确查询临床试验
- [ ] 根据therapy类型筛选试验
- [ ] qa_external模式下只返回最相关的1-2个试验
- [ ] report模式下提供完整的试验列表和分析

#### 3. Patent Expert
- [ ] 使用target+drug组合查询专利
- [ ] 根据intent判断是否需要专利布局分析
- [ ] comparison模式下对比不同target的专利数量

#### 4. Market Expert
- [ ] 结合disease评估市场规模
- [ ] 使用drug信息查询竞品
- [ ] qa模式下提供关键市场数据
- [ ] report模式下提供完整市场分析

### 优化实施步骤

1. **创建统一的Expert基类**
```python
class BaseExpert:
    async def analyze(self, params: Dict) -> Dict:
        # 解析参数
        intent_type = params['intent_type']
        entities = params['entities']
        query = params['original_query']
        
        # 根据intent调用不同方法
        if intent_type == 'report':
            return await self._generate_report_section(entities)
        elif intent_type == 'qa_external':
            return await self._answer_question(query, entities)
        elif intent_type == 'target_comparison':
            return await self._generate_comparison(entities)
```

2. **实现智能Prompt模板**
```python
def build_expert_prompt(expert_type, intent_type, entities, query):
    # 根据不同expert和intent生成定制化prompt
    pass
```

3. **添加结果后处理**
```python
def post_process_results(raw_results, intent_type):
    # 根据intent_type格式化输出
    pass
```

## 测试要点

### 已通过测试 ✅
- Control Agent意图识别
- State Machine工作流
- 缓存机制（4312倍加速）
- 基础的专家调度

### 待测试项目
- [ ] 子Expert参数注入
- [ ] 不同intent_type的返回格式
- [ ] Entity所有字段的利用率
- [ ] 检索精度提升效果

## 文件结构
```
agent_core/
├── agents/
│   ├── control_agent.py ✅
│   └── specialists/
│       ├── literature_expert.py 📝 待优化
│       ├── clinical_expert.py 📝 待优化
│       ├── patent_expert.py 📝 待优化
│       ├── market_expert.py 📝 待优化
│       └── editor_expert.py ✅
├── state_machine/
│   ├── graph_definition.py ✅
│   └── graph_runner.py ✅
└── prompts/
    └── control_prompts.py ✅
```

## 下次开发重点
1. 选择一个子Expert（建议从literature_expert开始）
2. 实现完整的参数接收和处理
3. 根据intent_type实现不同的返回格式
4. 测试优化效果
5. 复制模式到其他Expert

## 备注
- Control Agent和State Machine已稳定，不需要修改
- 重点是让子Expert更智能地利用传入的信息
- 每个Expert都应该能处理3种intent类型（除了qa_internal）