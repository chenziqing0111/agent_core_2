# agents/control_agent.py

"""
Control Agent - 理解用户意图，提取实体，调度专家
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from agent_core.clients.llm_client import LLMClient
from agent_core.agents.specialists.literature_expert import LiteratureExpert
# from agent_core.agents.specialists.clinical_expert import ClinicalExpert
# from agent_core.agents.specialists.patent_expert import PatentExpert


@dataclass
class Entity:
    """研究实体"""
    disease: Optional[str] = None
    target: Optional[str] = None
    drug: Optional[str] = None
    therapy: Optional[str] = None
    aliases: Dict[str, List[str]] = field(default_factory=dict)
    
    def has_content(self) -> bool:
        return any([self.disease, self.target, self.drug, self.therapy])
    
    def to_search_terms(self) -> List[str]:
        """所有搜索词，包括别名"""
        terms = []
        for field in ['disease', 'target', 'drug', 'therapy']:
            value = getattr(self, field)
            if value:
                terms.append(value)
                terms.extend(self.aliases.get(field, []))
        return list(set(terms))


class ControlAgent:
    """控制代理"""
    
    def __init__(self):
        self.llm = LLMClient()
        self.experts = {
            'literature': LiteratureExpert(),
            'clinical': ClinicalExpert(),
            'patent': PatentExpert()
        }
        
    async def process(self, user_input: str) -> Dict[str, Any]:
        """主流程"""
        intent = await self._parse_intent(user_input)
        
        if intent['entity'].has_content():
            intent['entity'] = await self._enrich_with_aliases(intent['entity'])
        
        results = await self._dispatch_experts(intent)
        
        return self._build_report(intent, results)
    
    async def _parse_intent(self, user_input: str) -> Dict[str, Any]:
        """解析意图和实体"""
        prompt = f"""
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
        
        try:
            response = await self.llm.generate_response(prompt, temperature=0.1)
            result = json.loads(response.strip())
            
            entity = Entity(**result.get('entity', {}))
            
            return {
                'entity': entity,
                'scope': result.get('scope', ['文献', '临床', '专利']),
                'focus': result.get('focus', user_input),
                'query': user_input
            }
        except:
            return {
                'entity': Entity(),
                'scope': ['文献', '临床', '专利'],
                'focus': user_input,
                'query': user_input
            }
    
    async def _enrich_with_aliases(self, entity: Entity) -> Entity:
        """获取别名"""
        items = []
        for field in ['disease', 'target', 'drug', 'therapy']:
            value = getattr(self, field)
            if value:
                items.append(f"{field}: {value}")
        
        if not items:
            return entity
        
        prompt = f"""
为以下术语提供常用别名和同义词：

{chr(10).join(items)}

返回JSON格式的别名字典，每项最多5个别名。
"""
        
        try:
            response = await self.llm.generate_response(prompt, temperature=0.1)
            entity.aliases = json.loads(response.strip())
        except:
            pass
            
        return entity
    
    async def _dispatch_experts(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """调度专家"""
        search_params = {
            'entity': intent['entity'],
            'search_terms': intent['entity'].to_search_terms(),
            'focus': intent['focus']
        }
        
        tasks = {}
        scope_map = {'文献': 'literature', '临床': 'clinical', '专利': 'patent'}
        
        for scope_name in intent['scope']:
            if scope_name in scope_map:
                expert_key = scope_map[scope_name]
                tasks[expert_key] = self.experts[expert_key].analyze(**search_params)
        
        results = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception as e:
                print(f"✗ {name}: {e}")
                results[name] = None
                
        return results
    
    def _build_report(self, intent: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """构建报告"""
        entity = intent['entity']
        
        return {
            'query': intent['query'],
            'focus': intent['focus'],
            'entity': {
                'disease': entity.disease,
                'target': entity.target,
                'drug': entity.drug,
                'therapy': entity.therapy,
                'search_terms': entity.to_search_terms()
            },
            'results': results,
            'summary': self._make_summary(entity, results),
            'timestamp': datetime.now().isoformat()
        }
    
    def _make_summary(self, entity: Entity, results: Dict[str, Any]) -> str:
        """生成摘要"""
        parts = []
        
        # 实体描述
        entities = []
        if entity.target:
            entities.append(entity.target)
        if entity.therapy:
            entities.append(entity.therapy)
        if entity.disease:
            entities.append(f"in {entity.disease}")
        if entity.drug:
            entities.append(f"({entity.drug})")
            
        if entities:
            parts.append(" ".join(entities))
        
        # 结果统计
        stats = []
        for key, label in [('literature', 'papers'), ('clinical', 'trials'), ('patent', 'patents')]:
            if results.get(key):
                count = results[key].get(f'total_{label}', 0)
                if count:
                    stats.append(f"{count} {label}")
        
        if stats:
            parts.append(f"[{', '.join(stats)}]")
        
        return " - ".join(parts)


# LangGraph 集成
from langgraph.graph import StateGraph, END
from typing import TypedDict


class State(TypedDict):
    user_input: str
    intent: Dict
    results: Dict
    report: Dict


def create_graph():
    """创建工作流"""
    workflow = StateGraph(State)
    control = ControlAgent()
    
    async def parse(state: State) -> State:
        state['intent'] = await control._parse_intent(state['user_input'])
        return state
    
    async def enrich(state: State) -> State:
        if state['intent']['entity'].has_content():
            state['intent']['entity'] = await control._enrich_with_aliases(
                state['intent']['entity']
            )
        return state
    
    async def analyze(state: State) -> State:
        state['results'] = await control._dispatch_experts(state['intent'])
        return state
    
    async def report(state: State) -> State:
        state['report'] = control._build_report(state['intent'], state['results'])
        return state
    
    workflow.add_node("parse", parse)
    workflow.add_node("enrich", enrich)
    workflow.add_node("analyze", analyze)
    workflow.add_node("report", report)
    
    workflow.add_edge("parse", "enrich")
    workflow.add_edge("enrich", "analyze")
    workflow.add_edge("analyze", "report")
    workflow.add_edge("report", END)
    
    workflow.set_entry_point("parse")
    
    return workflow.compile()