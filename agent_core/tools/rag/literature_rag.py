# agent_core/tools/rag/literature_rag.py

"""
Literature RAG - 文献RAG处理模块
负责：文本分块、向量索引、相似度检索
纯RAG功能，不涉及业务逻辑
"""

import os
import numpy as np
from typing import List, Dict, Any, Tuple, Optional, Callable
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import faiss
import hashlib
import pickle

from agent_core.config.settings import config


@dataclass
class TextChunk:
    """文本块数据结构"""
    text: str
    doc_id: str  # PMID
    chunk_id: str
    metadata: Dict
    start_idx: int = 0
    end_idx: int = 0
    embedding: Optional[np.ndarray] = None
    score: float = 0.0  # 相似度分数


class LiteratureRAG:
    """文献RAG处理器 - 纯检索功能"""
    
    def __init__(self):
        # 初始化模型
        self._init_model()
        
        # 索引和数据
        self.index = None
        self.chunks = []
        self.articles = []
        
        # 改进的chunk参数
        self.chunk_size = 400  # 400词
        self.chunk_overlap = 100  # 100词重叠
        self.min_chunk_size = 50  # 最小chunk大小
        
        # 缓存设置
        self.cache_dir = "rag_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _init_model(self):
        """初始化嵌入模型"""
        model_path = config.embedding_model_path
        
        if os.path.exists(model_path):
            print(f"[RAG] Loading model from: {model_path}")
            self.model = SentenceTransformer(model_path)
        else:
            print(f"[RAG] Loading model: {config.embedding_model}")
            self.model = SentenceTransformer(config.embedding_model)
            
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"[RAG] Model initialized with dimension: {self.embedding_dim}")
    
    def process_articles(self, articles: List[Any]) -> None:
        """
        处理文章列表：创建块并构建索引
        
        Args:
            articles: 文章列表
        """
        if not articles:
            print("[RAG] No articles to process")
            return
            
        self.articles = articles
        
        # 生成缓存键
        cache_key = self._get_cache_key(articles)
        
        # 尝试加载缓存
        if self._load_cache(cache_key):
            print(f"[RAG] Loaded from cache: {cache_key}")
            return
        
        # 创建文本块
        self.chunks = self.create_chunks(articles)
        
        # 构建索引
        if self.chunks:
            self.build_index(self.chunks)
            # 保存缓存
            self._save_cache(cache_key)
        
        print(f"[RAG] Processed {len(articles)} articles into {len(self.chunks)} chunks")
    
    def create_chunks(self, articles: List[Any]) -> List[TextChunk]:
        """
        创建文本块
        
        Args:
            articles: 文章列表
            
        Returns:
            文本块列表
        """
        chunks = []
        
        for idx, article in enumerate(articles):
            # 获取文章内容
            pmid = getattr(article, 'pmid', f"unknown_{idx}")
            title = getattr(article, 'title', '')
            abstract = getattr(article, 'abstract', '')
            
            # 组合标题和摘要
            full_text = f"{title}\n\n{abstract}".strip()
            
            if not full_text:
                continue
            
            # 按词分割
            words = full_text.split()
            
            # 如果文本太短，作为单个chunk
            if len(words) <= self.chunk_size:
                if len(words) >= self.min_chunk_size:
                    chunk_id = self._generate_chunk_id(pmid, 0, full_text)
                    chunks.append(self._create_chunk(
                        text=full_text,
                        doc_id=pmid,
                        chunk_id=chunk_id,
                        article=article,
                        start_idx=0,
                        end_idx=len(words)
                    ))
            else:
                # 滑动窗口创建块
                step = self.chunk_size - self.chunk_overlap
                for i in range(0, len(words), step):
                    chunk_words = words[i:i + self.chunk_size]
                    
                    # 过滤太短的chunk
                    if len(chunk_words) < self.min_chunk_size:
                        continue
                    
                    chunk_text = " ".join(chunk_words)
                    chunk_id = self._generate_chunk_id(pmid, i, chunk_text)
                    
                    chunks.append(self._create_chunk(
                        text=chunk_text,
                        doc_id=pmid,
                        chunk_id=chunk_id,
                        article=article,
                        start_idx=i,
                        end_idx=min(i + self.chunk_size, len(words))
                    ))
        
        print(f"[RAG] Created {len(chunks)} chunks from {len(articles)} articles")
        return chunks
    
    def build_index(self, chunks: List[TextChunk]) -> None:
        """
        构建FAISS向量索引
        
        Args:
            chunks: 文本块列表
        """
        if not chunks:
            print("[RAG] No chunks to index")
            return
        
        print(f"[RAG] Building index for {len(chunks)} chunks...")
        
        # 批量编码
        texts = [c.text for c in chunks]
        embeddings = self._batch_encode(texts)
        
        # 保存嵌入到chunks
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]
        
        # 创建FAISS索引（内积用于余弦相似度）
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        
        # 归一化并添加到索引
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        self.chunks = chunks
        print(f"[RAG] Index built successfully")
    
    def search(self, query: str, top_k: int = 10, 
              threshold: float = 0.0) -> List[TextChunk]:
        """
        搜索相关文本块
        
        Args:
            query: 查询字符串
            top_k: 返回结果数
            threshold: 相似度阈值
            
        Returns:
            相关文本块列表（按相似度降序）
        """
        if not self.index or not self.chunks:
            print("[RAG] No index available for search")
            return []
        
        # 编码查询
        query_embedding = self.model.encode([query], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # 搜索
        k = min(top_k, len(self.chunks))
        distances, indices = self.index.search(query_embedding, k)
        
        # 过滤并返回结果
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.chunks) and dist > threshold:
                chunk = self.chunks[idx]
                chunk.score = float(dist)
                results.append(chunk)
        
        return results
    
    def retrieve_for_dimension(self, query: str, 
                               top_k: int = 15,
                               expand_query_fn: Optional[Callable] = None,
                               score_threshold: float = 0.3,
                               max_per_pmid: int = 3) -> Tuple[List[TextChunk], str]:
        """
        检索相关内容
        
        Args:
            query: 查询字符串
            top_k: 初始返回结果数
            expand_query_fn: 扩展查询的函数（可选）
            score_threshold: 相似度阈值
            max_per_pmid: 每个PMID最多返回的chunks数
            
        Returns:
            (相关块列表, 格式化的上下文)
        """
        # 主查询
        relevant_chunks = self.search(query, top_k=top_k, threshold=score_threshold)
        
        # 如果结果不足且提供了扩展函数，尝试扩展查询
        if len(relevant_chunks) < 3 and expand_query_fn:
            try:
                expanded_query = expand_query_fn()
                if expanded_query and expanded_query != query:
                    additional_chunks = self.search(
                        expanded_query, 
                        top_k=5, 
                        threshold=score_threshold * 0.8  # 稍微放宽阈值
                    )
                    
                    # 合并结果（去重）
                    seen_ids = {c.chunk_id for c in relevant_chunks}
                    for chunk in additional_chunks:
                        if chunk.chunk_id not in seen_ids:
                            relevant_chunks.append(chunk)
                            seen_ids.add(chunk.chunk_id)
            except Exception as e:
                print(f"[RAG] Expand query failed: {e}")
        
        # 按相关性分数重新排序
        relevant_chunks = sorted(relevant_chunks, key=lambda x: x.score, reverse=True)
        
        # 限制每个PMID的chunks数量（保留最相关的）
        if max_per_pmid:
            relevant_chunks = self._limit_chunks_per_pmid(relevant_chunks, max_per_pmid)
        
        # 格式化上下文
        formatted_context = self._format_context(relevant_chunks)
        
        return relevant_chunks, formatted_context
    
    def _limit_chunks_per_pmid(self, chunks: List[TextChunk], 
                               max_per_pmid: int) -> List[TextChunk]:
        """
        限制每个PMID的chunks数量
        
        Args:
            chunks: 文本块列表
            max_per_pmid: 每个PMID最多保留的chunks数
            
        Returns:
            限制后的chunks列表
        """
        pmid_chunks = {}
        
        # 按PMID分组
        for chunk in chunks:
            pmid = chunk.doc_id
            if pmid not in pmid_chunks:
                pmid_chunks[pmid] = []
            pmid_chunks[pmid].append(chunk)
        
        # 每个PMID保留最相关的N个
        limited_chunks = []
        for pmid, pmid_chunk_list in pmid_chunks.items():
            # 按相关性排序，取前N个
            pmid_chunk_list = sorted(pmid_chunk_list, key=lambda x: x.score, reverse=True)
            limited_chunks.extend(pmid_chunk_list[:max_per_pmid])
        
        # 重新按整体相关性排序
        return sorted(limited_chunks, key=lambda x: x.score, reverse=True)
    
    def _format_context(self, chunks: List[TextChunk]) -> str:
        """
        格式化上下文（纯文本，不添加引用标记）
        
        Args:
            chunks: 文本块列表
            
        Returns:
            格式化的上下文字符串
        """
        if not chunks:
            return ""
        
        # 按相关性排序的文本块
        formatted_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            # 添加分隔符和文本
            formatted_parts.append(f"[Segment {i}]\n{chunk.text}")
        
        return "\n\n---\n\n".join(formatted_parts)
    
    # ============ 辅助方法 ============
    
    def _generate_chunk_id(self, doc_id: str, position: int, text: str) -> str:
        """生成chunk ID"""
        unique_str = f"{doc_id}_{position}_{text[:50]}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def _create_chunk(self, text: str, doc_id: str, chunk_id: str,
                     article: Any, start_idx: int, end_idx: int) -> TextChunk:
        """创建单个chunk"""
        metadata = {
            'title': getattr(article, 'title', '')[:200],
            'year': getattr(article, 'year', 0),
            'journal': getattr(article, 'journal', ''),
            'authors': getattr(article, 'authors', [])[:3],
            'keywords': getattr(article, 'keywords', []),
            'mesh_terms': getattr(article, 'mesh_terms', [])
        }
        
        return TextChunk(
            text=text,
            doc_id=doc_id,
            chunk_id=chunk_id,
            metadata=metadata,
            start_idx=start_idx,
            end_idx=end_idx
        )
    
    def _batch_encode(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """批量编码文本"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            embeddings.append(batch_embeddings)
        
        return np.vstack(embeddings).astype('float32')
    
    # ============ 缓存方法 ============
    
    def _get_cache_key(self, articles: List[Any]) -> str:
        """生成缓存键"""
        pmids = []
        for idx, article in enumerate(articles):
            pmid = getattr(article, 'pmid', None)
            if pmid:
                pmids.append(pmid)
            else:
                pmids.append(f"article_{idx}")
        
        pmids = sorted(pmids[:20])  # 使用前20个PMID
        key_str = "_".join(pmids)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _save_cache(self, cache_key: str) -> None:
        """保存缓存"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({
                    'chunks': self.chunks,
                    'index': faiss.serialize_index(self.index) if self.index else None
                }, f)
            print(f"[RAG] Cache saved: {cache_key}")
        except Exception as e:
            print(f"[RAG] Failed to save cache: {e}")
    
    def _load_cache(self, cache_key: str) -> bool:
        """加载缓存"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.pkl")
        
        if not os.path.exists(cache_file):
            return False
        
        try:
            with open(cache_file, 'rb') as f:
                data = pickle.load(f)
                self.chunks = data['chunks']
                if data['index']:
                    self.index = faiss.deserialize_index(data['index'])
            return True
        except Exception as e:
            print(f"[RAG] Failed to load cache: {e}")
            return False
    
    def clear_cache(self) -> None:
        """清空缓存"""
        import shutil
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
        print("[RAG] Cache cleared")
    
    # ============ 统计方法 ============
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取RAG统计信息"""
        if not self.chunks:
            return {"status": "No data indexed"}
        
        pmid_count = len(set(c.doc_id for c in self.chunks))
        
        return {
            "total_articles": len(self.articles),
            "total_chunks": len(self.chunks),
            "unique_pmids": pmid_count,
            "avg_chunks_per_article": len(self.chunks) / len(self.articles) if self.articles else 0,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "index_dimension": self.embedding_dim
        }