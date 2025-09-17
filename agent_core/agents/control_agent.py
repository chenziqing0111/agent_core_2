# agent_core/agents/control_agent.py

"""
Control Agent - 中央控制器
负责意图识别、实体提取、专家调度、结果整合
与state_machine模块配合使用
"""

import json
import asyncio
from typing import Union,Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from agent_core.clients.llm_client import LLMClient
from agent_core.prompts.control_prompts import (
    get_intent_parsing_prompt,
    get_memory_search_prompt,
    get_expert_aggregation_prompt
)

# 导入各专家Agent
from agent_core.agents.specialists.literature_expert import LiteratureExpert
from agent_core.agents.specialists.clinical_expert import ClinicalExpert
from agent_core.agents.specialists.patent_expert import PatentExpert
from agent_core.agents.specialists.market_expert import MarketExpert
from agent_core.agents.specialists.editor_expert import EditorAgent


class IntentType(Enum):
    """意图类型枚举"""
    REPORT = "report"              # 完整报告
    QA_EXTERNAL = "qa_external"    # 外部问题
    QA_INTERNAL = "qa_internal"    # 内部问题
    TARGET_COMPARISON = "target_comparison"  # 靶点对比


@dataclass
class Entity:
    """实体数据类"""
    target: Optional[Union[str, Dict[str, Any]]] = None
    disease: Optional[Union[str, Dict[str, Any]]] = None
    drug: Optional[Union[str, Dict[str, Any]]] = None
    therapy: Optional[Union[str, Dict[str, Any]]] = None
    
    def get_primary(self, field: str) -> Optional[str]:
        """获取主名称"""
        value = getattr(self, field, None)
        if isinstance(value, dict):
            return value.get('primary')
        return value
    
    def get_aliases(self, field: str) -> List[str]:
        """获取别名列表"""
        value = getattr(self, field, None)
        if isinstance(value, dict):
            return value.get('aliases', [])
        return []
    
    def to_dict(self) -> dict:
        """转换为字典（兼容新旧格式）"""
        result = {}
        for field in ['target', 'disease', 'drug', 'therapy']:
            value = getattr(self, field, None)
            if value is not None:
                result[field] = value
        return result

@dataclass
class ParsedIntent:
    """解析后的意图"""
    intent_type: IntentType
    confidence: float
    entities: Entity
    relevant_experts: List[str]
    reasoning: str
    original_query: str


class MemoryManager:
    """记忆管理器"""
    def __init__(self):
        self.conversation_history: List[Dict] = []
        self.cached_results: Dict[str, Any] = {}
        self.generated_reports: Dict[str, str] = {}
    
    def add_interaction(self, query: str, response: Any, intent_type: str):
        """添加交互记录"""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response": response,
            "intent_type": intent_type
        })
    
    def get_relevant_context(self, query: str, limit: int = 5) -> str:
        """获取相关上下文"""
        recent = self.conversation_history[-limit:] if self.conversation_history else []
        context_parts = []
        
        for item in recent:
            query_text = item['query']
            response = item.get('response', '')
            
            # 处理不同类型的response
            if isinstance(response, dict):
                # 如果是字典，转换为字符串
                response_text = str(response)[:500]
            elif isinstance(response, str):
                # 如果是字符串，直接使用
                response_text = response[:500]
            else:
                # 其他类型，转换为字符串
                response_text = str(response)[:500]
            
            context_parts.append(f"Q: {query_text}\nA: {response_text}")
        
        context = "\n".join(context_parts)
        return context
    
    def cache_results(self, key: str, results: Any):
        """缓存查询结果"""
        self.cached_results[key] = {
            "data": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_cached_results(self, key: str) -> Optional[Any]:
        """获取缓存结果"""
        if key in self.cached_results:
            # 可以添加过期检查逻辑
            return self.cached_results[key]["data"]
        return None
    
    def store_report(self, report_id: str, report_content: str):
        """存储生成的报告"""
        self.generated_reports[report_id] = {
            "content": report_content,
            "timestamp": datetime.now().isoformat()
        }


class ControlAgent:
    """中央控制代理 - 提供给state_machine调用的方法"""
    
    def __init__(self):
        self.llm = LLMClient()
        self.memory = MemoryManager()
        
        # 初始化数据收集专家
        self.data_experts = {
            "literature_expert": LiteratureExpert(),
            "clinical_expert": ClinicalExpert(),
            "patent_expert": PatentExpert(),
            "market_expert": MarketExpert()
        }
        
        # 初始化报告编辑专家
        self.editor_expert = EditorAgent()
    
    async def parse_intent(self, user_input: str) -> ParsedIntent:
        """
        解析用户意图、提取实体、选择专家
        一次LLM调用完成所有任务
        
        供state_machine调用
        """
        prompt = get_intent_parsing_prompt(user_input)
        
        try:
            response = await self.llm.generate_response(prompt)
            parsed = json.loads(response)
            
            return ParsedIntent(
                intent_type=IntentType(parsed["intent_type"]),
                confidence=parsed.get("confidence", 0.8),
                entities=Entity(**parsed.get("entities", {})),
                relevant_experts=parsed.get("relevant_experts", []),
                reasoning=parsed.get("reasoning", ""),
                original_query=user_input
            )
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            # 默认为report类型
            return ParsedIntent(
                intent_type=IntentType.REPORT,
                confidence=0.5,
                entities=Entity(),
                relevant_experts=list(self.data_experts.keys()),
                reasoning="解析失败，默认为完整报告",
                original_query=user_input
            )
    
    async def handle_internal_qa(self, parsed_intent: ParsedIntent) -> str:
        """
        处理内部问题（基于记忆回答）
        
        供state_machine调用
        """
        context = self.memory.get_relevant_context(parsed_intent.original_query)
        
        if not context:
            return "抱歉，我没有找到相关的历史信息来回答这个问题。需要我重新查询吗？"
        
        prompt = get_memory_search_prompt(
            parsed_intent.original_query,
            context
        )
        
        return await self.llm.generate_response(prompt)
    
    async def collect_data_from_experts(self, 
                                       parsed_intent: ParsedIntent) -> Dict[str, Any]:
        """
        统一的数据收集方法
        report和qa_external共享同一套检索系统
        
        供state_machine调用
        """
        # 构建统一的参数（包含intent_type，让子expert自己决定返回格式）
        expert_params = {
            "intent_type": parsed_intent.intent_type.value,
            "original_query": parsed_intent.original_query,
            "entities": parsed_intent.entities.to_dict()
        }
        
        # 检查缓存
        cache_key = self._generate_cache_key(expert_params)
        cached = self.memory.get_cached_results(cache_key)
        if cached:
            print("✓ 使用缓存数据")
            return cached
        
        # 并行调用选定的专家
        tasks = {}
        for expert_name in parsed_intent.relevant_experts:
            if expert_name in self.data_experts:
                expert = self.data_experts[expert_name]
                # 每个专家根据intent_type自行决定返回格式
                tasks[expert_name] = expert.analyze(expert_params)
        
        if not tasks:
            return {}
        
        # 并行执行
        results = {}
        for expert_name, task in tasks.items():
            try:
                results[expert_name] = await task
                print(f"✓ {expert_name} 完成数据收集")
            except Exception as e:
                print(f"✗ {expert_name} 数据收集失败: {e}")
                results[expert_name] = None
        
        # 过滤掉失败的结果
        valid_results = {k: v for k, v in results.items() if v is not None}
        
        # 缓存结果
        if valid_results:
            self.memory.cache_results(cache_key, valid_results)
        
        return valid_results
    
    async def generate_report(self, 
                            data_results: Dict[str, Any],
                            parsed_intent: ParsedIntent) -> str:
        """
        使用Editor Expert生成报告
        
        供state_machine调用（仅report类型）
        """
        # 生成报告标题
        title = self._generate_report_title(parsed_intent.entities)
        
        # 调用Editor Expert生成HTML报告
        report_html = self.editor_expert.generate_report(
            agents_results=data_results,
            gene_target=parsed_intent.entities.get_primary('target') or "目标",
            title=title
        )
        
        # 存储报告
        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.memory.store_report(report_id, report_html)
        
        return report_html
    
    async def aggregate_qa_response(self,
                                  data_results: Dict[str, Any],
                                  parsed_intent: ParsedIntent) -> str:
        """
        整合QA类型的响应（qa_external和target_comparison）
        
        供state_machine调用
        """
        if parsed_intent.intent_type == IntentType.QA_EXTERNAL:
            # 直接针对问题回答
            prompt = get_expert_aggregation_prompt(
                data_results,
                "qa_external",
                parsed_intent.original_query
            )
            return await self.llm.generate_response(prompt)
            
        elif parsed_intent.intent_type == IntentType.TARGET_COMPARISON:
            # 对比分析
            prompt = get_expert_aggregation_prompt(
                data_results,
                "target_comparison", 
                parsed_intent.original_query
            )
            return await self.llm.generate_response(prompt)
        
        return "无法处理的查询类型"
    
    def _generate_report_title(self, entities: Entity) -> str:
        """生成报告标题"""
        parts = []
        if entities.target:
            target_name = entities.get_primary('target')
            if target_name:
                parts.append(target_name)
        if entities.disease:
            desease_name = entities.get_primary('disease')
            if desease_name:
                parts.append(desease_name)
        if entities.therapy:
            therapy_name = entities.get_primary('therapy')
            if therapy_name:
                parts.append(therapy_name)
        if entities.drug:
            drug_name = entities.get_primary('drug')
            if drug_name:
                parts.append(drug_name)

        if parts:
            return "-".join(parts) + "研究报告"
        else:
            return "生物医学研究报告"
    
    def _generate_cache_key(self, params: Dict) -> str:
        """生成缓存键"""
        entities = params.get("entities", {})
        entities_key = ""
    
        for field in ['target', 'disease', 'drug', 'therapy']:
            value = entities.get(field)
            if value:
                if isinstance(value, dict):
                    # 新格式：使用 primary 名称
                    entities_key += f"{field}:{value.get('primary', '')}|"
                else:
                    # 旧格式：直接使用值
                    entities_key += f"{field}:{value}|"
    
        key_parts = [
            params.get("intent_type", ""),
            entities_key,
        ]
        return "|".join(filter(None, key_parts))
    
    def save_interaction(self, query: str, response: Any, intent_type: str):
        """
        保存交互记录
        
        供state_machine调用
        """
        self.memory.add_interaction(query, response, intent_type)


# 导出
__all__ = [
    'ControlAgent',
    'IntentType',
    'Entity', 
    'ParsedIntent',
    'MemoryManager'
]