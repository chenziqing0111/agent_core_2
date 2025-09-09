# agent_core/config/settings.py

"""
配置文件
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """全局配置"""
    # PubMed配置
    pubmed_email: str = "czqrainy@gmail.com"
    pubmed_api_key: str = "983222f9d5a2a81facd7d158791d933e6408"
    
    # 检索配置
    max_articles: int = 100
    max_chunks_per_query: int = 10
    
    # 模型配置
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_path: str = ''
    # LLM配置
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096


# 全局配置实例
config = Config()