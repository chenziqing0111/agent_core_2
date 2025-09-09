# agent_core/tools/rag/rag_processor.py

"""
RAG Processor for Literature
"""

import os
import numpy as np
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import faiss
import hashlib

from agent_core.config.settings import config


@dataclass
class TextChunk:
    text: str
    doc_id: str
    chunk_id: str
    metadata: Dict


class LiteratureRAG:
    """文献RAG处理器"""
    
    def __init__(self):
        # 使用配置中的模型路径
        model_path = config.embedding_model_path
        
        # 检查路径是否存在
        if os.path.exists(model_path):
            print(f"[RAG] Loading model from: {model_path}")
            self.model = SentenceTransformer(model_path)
        else:
            print(f"[RAG] Model path not found: {model_path}")
            print(f"[RAG] Trying to load from default: {config.embedding_model}")
            self.model = SentenceTransformer(config.embedding_model)
            
        self.index = None
        self.chunks = []
        
    def create_chunks(self, articles: List[Any], chunk_size: int = 500) -> List[TextChunk]:
        """创建文本块"""
        chunks = []
        
        for article in articles:
            text = f"{article.title}\n\n{article.abstract}"
            
            # 简单分块
            words = text.split()
            for i in range(0, len(words), chunk_size):
                chunk_text = " ".join(words[i:i+chunk_size])
                chunk_id = hashlib.md5(f"{article.pmid}_{i}".encode()).hexdigest()[:8]
                
                chunks.append(TextChunk(
                    text=chunk_text,
                    doc_id=article.pmid,
                    chunk_id=chunk_id,
                    metadata={
                        'title': article.title,
                        'year': article.year,
                        'journal': article.journal
                    }
                ))
        
        self.chunks = chunks
        return chunks
    
    def build_index(self, chunks: List[TextChunk]):
        """构建向量索引"""
        if not chunks:
            return
        
        texts = [c.text for c in chunks]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings.astype('float32'))
    
    def search(self, query: str, top_k: int = 10) -> List[TextChunk]:
        """搜索相关块"""
        if not self.index or not self.chunks:
            return []
        
        query_embedding = self.model.encode([query], show_progress_bar=False)
        distances, indices = self.index.search(
            query_embedding.astype('float32'),
            min(top_k, len(self.chunks))
        )
        
        results = []
        for idx in indices[0]:
            if idx < len(self.chunks):
                results.append(self.chunks[idx])
        
        return results
    
    def get_context(self, question: str, entity: Any, top_k: int = 10) -> Tuple[List[TextChunk], str]:
        """获取问题相关上下文"""
        
        # 根据问题类型构建查询
        queries = self._build_queries(question, entity)
        
        # 检索
        all_chunks = []
        for query in queries:
            chunks = self.search(query, top_k=top_k//len(queries))
            all_chunks.extend(chunks)
        
        # 去重
        seen = set()
        unique = []
        for chunk in all_chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                unique.append(chunk)
        
        # 格式化
        context = self._format_context(unique[:top_k])
        
        return unique[:top_k], context
    
    def _build_queries(self, question: str, entity: Any) -> List[str]:
        """构建查询"""
        queries = []
        
        if "mechanism" in question.lower():
            if entity.disease and entity.target:
                queries.append(f"{entity.target} {entity.disease} mechanism pathway")
            queries.append("molecular mechanism signaling")
            
        elif "treatment" in question.lower():
            if entity.disease:
                queries.append(f"{entity.disease} treatment therapy clinical")
            if entity.therapy:
                queries.append(f"{entity.therapy} efficacy safety")
                
        elif "target" in question.lower():
            if entity.target:
                queries.append(f"{entity.target} druggability binding")
            queries.append("drug target validation")
        
        if not queries:
            queries.append(question)
        
        return queries
    
    def _format_context(self, chunks: List[TextChunk]) -> str:
        """格式化上下文"""
        if not chunks:
            return ""
        
        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"文献{i} [PMID:{chunk.doc_id}]:\n{chunk.text}")
        
        return "\n---\n".join(parts)