# agent_core/state_machine/graph_definition.py

"""
工作流定义 - 简化版
只负责流程编排，业务逻辑完全交给Control Agent
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any


class AgentState(TypedDict):
    """工作流状态"""
    user_input: str
    parsed_intent: Optional[Any]  # ParsedIntent对象
    data_results: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]


def create_workflow(control_agent):
    """
    创建工作流
    
    Args:
        control_agent: ControlAgent实例
    """
    workflow = StateGraph(AgentState)
    
    # ===== 极简节点定义（只调用Control Agent方法） =====
    
    async def parse_intent(state: AgentState) -> AgentState:
        """解析意图"""
        state["parsed_intent"] = await control_agent.parse_intent(state["user_input"])
        return state
    
    async def handle_internal_qa(state: AgentState) -> AgentState:
        """内部QA - Control Agent处理所有逻辑"""
        content = await control_agent.handle_internal_qa(state["parsed_intent"])
        state["final_response"] = {
            "type": "qa_internal",
            "content": content
        }
        return state
    
    async def collect_data(state: AgentState) -> AgentState:
        """数据收集 - Control Agent处理所有逻辑"""
        state["data_results"] = await control_agent.collect_data_from_experts(
            state["parsed_intent"]
        )
        return state
    
    async def generate_report(state: AgentState) -> AgentState:
        """生成报告 - Control Agent处理所有逻辑"""
        report_html = await control_agent.generate_report(
            state["data_results"],
            state["parsed_intent"]
        )
        state["final_response"] = {
            "type": "report",
            "html_content": report_html
        }
        return state
    
    async def aggregate_qa(state: AgentState) -> AgentState:
        """整合QA响应 - Control Agent处理所有逻辑"""
        content = await control_agent.aggregate_qa_response(
            state["data_results"],
            state["parsed_intent"]
        )
        state["final_response"] = {
            "type": state["parsed_intent"].intent_type.value,
            "content": content
        }
        return state
    
    async def save_interaction(state: AgentState) -> AgentState:
        """保存交互"""
        control_agent.save_interaction(
            state["user_input"],
            state["final_response"],
            state["parsed_intent"].intent_type.value
        )
        return state
    
    # ===== 简单路由 =====
    
    def route_after_parse(state: AgentState) -> str:
        """根据意图类型路由"""
        intent_type = state["parsed_intent"].intent_type.value
        
        if intent_type == "qa_internal":
            return "handle_internal_qa"
        else:
            return "collect_data"
    
    def route_after_data(state: AgentState) -> str:
        """数据收集后路由"""
        intent_type = state["parsed_intent"].intent_type.value
        
        if intent_type == "report":
            return "generate_report"
        else:
            return "aggregate_qa"
    
    # ===== 构建工作流 =====
    
    # 添加节点
    workflow.add_node("parse_intent", parse_intent)
    workflow.add_node("handle_internal_qa", handle_internal_qa)
    workflow.add_node("collect_data", collect_data)
    workflow.add_node("generate_report", generate_report)
    workflow.add_node("aggregate_qa", aggregate_qa)
    workflow.add_node("save_interaction", save_interaction)
    
    # 设置流程
    workflow.set_entry_point("parse_intent")
    
    workflow.add_conditional_edges(
        "parse_intent",
        route_after_parse,
        {
            "handle_internal_qa": "handle_internal_qa",
            "collect_data": "collect_data"
        }
    )
    
    workflow.add_conditional_edges(
        "collect_data",
        route_after_data,
        {
            "generate_report": "generate_report",
            "aggregate_qa": "aggregate_qa"
        }
    )
    
    workflow.add_edge("handle_internal_qa", "save_interaction")
    workflow.add_edge("generate_report", "save_interaction")
    workflow.add_edge("aggregate_qa", "save_interaction")
    workflow.add_edge("save_interaction", END)
    
    return workflow.compile()