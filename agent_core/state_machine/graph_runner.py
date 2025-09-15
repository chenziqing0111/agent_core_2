# agent_core/state_machine/graph_runner.py

"""
工作流运行器 - 简化版
"""

import asyncio
from typing import Dict, Any, Optional
from agent_core.agents.control_agent import ControlAgent
from agent_core.state_machine.graph_definition import create_workflow, AgentState


class WorkflowRunner:
    """工作流运行器"""
    
    def __init__(self):
        self.control_agent = ControlAgent()
        self.workflow = create_workflow(self.control_agent)
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        """
        运行工作流
        
        Args:
            user_input: 用户输入
            
        Returns:
            处理结果
        """
        # 初始状态
        initial_state: AgentState = {
            "user_input": user_input,
            "parsed_intent": None,
            "data_results": None,
            "final_response": None
        }
        
        try:
            # 执行工作流
            final_state = await self.workflow.ainvoke(initial_state)
            
            return {
                "success": True,
                "query": user_input,
                "intent": {
                    "type": final_state["parsed_intent"].intent_type.value,
                    "confidence": final_state["parsed_intent"].confidence,
                    "entities": final_state["parsed_intent"].entities.to_dict()
                },
                "response": final_state["final_response"]
            }
            
        except Exception as e:
            # 错误处理全部在Control Agent内部
            return {
                "success": False,
                "error": str(e),
                "query": user_input
            }


# 便捷函数
async def process_query(user_input: str) -> Dict[str, Any]:
    """处理用户查询的便捷接口"""
    runner = WorkflowRunner()
    return await runner.run(user_input)


# 测试
async def test():
    """简单测试"""
    queries = [
        "帮我做一份PD-1靶点的完整调研报告",
        "KRAS G12C抑制剂最新的临床试验进展如何？",
        "刚才提到的副作用具体是什么？"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        result = await process_query(query)
        print(f"意图: {result.get('intent', {}).get('type')}")
        print(f"成功: {result.get('success')}")


if __name__ == "__main__":
    asyncio.run(test())