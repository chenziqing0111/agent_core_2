# agent_core/tools/rag/literature_rag.py

"""
Literature RAG - 文献RAG处理模块
负责：文本分块、向量索引、相似度检索、上下文格式化
"""

import os
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
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
    doc_id: str
    chunk_id: str
    metadata: Dict
    start_idx: int = 0
    end_idx: int = 0
    embedding: Optional[np.ndarray] = None


class LiteratureRAG:
    """文献RAG处理器"""
    
    def __init__(self):
        # 初始化模型
        self._init_model()
        
        # 索引和数据
        self.index = None
        self.chunks = []
        self.articles = []
        
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
    
    def process_articles(self, articles: List[Any]) -> None:
        """
        处理文章列表：创建块并构建索引
        
        Args:
            articles: 文章列表
        """
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
        self.build_index(self.chunks)
        
        # 保存缓存
        self._save_cache(cache_key)
        
        print(f"[RAG] Processed {len(articles)} articles into {len(self.chunks)} chunks")
    
    def create_chunks(self, articles: List[Any], chunk_size: int = 250, 
                     chunk_overlap: int = 50) -> List[TextChunk]:
        """
        创建文本块（带重叠）
        
        Args:
            articles: 文章列表
            chunk_size: 块大小（词数）
            chunk_overlap: 重叠大小（词数）
            
        Returns:
            文本块列表
        """
        chunks = []
        
        for article in articles:
            # 组合标题和摘要
            full_text = f"{article.title}\n\n{article.abstract}"
            words = full_text.split()
            
            # 滑动窗口创建块
            for i in range(0, len(words), chunk_size - chunk_overlap):
                chunk_words = words[i:i + chunk_size]
                chunk_text = " ".join(chunk_words)
                
                # 生成chunk ID
                chunk_id = hashlib.md5(
                    f"{article.pmid}_{i}_{chunk_text[:50]}".encode()
                ).hexdigest()[:8]
                
                # 创建元数据
                metadata = {
                    'title': article.title[:200],
                    'year': article.year,
                    'journal': article.journal,
                    'authors': article.authors[:3] if hasattr(article, 'authors') else [],
                    'keywords': getattr(article, 'keywords', []),
                    'mesh_terms': getattr(article, 'mesh_terms', [])
                }
                
                chunks.append(TextChunk(
                    text=chunk_text,
                    doc_id=article.pmid,
                    chunk_id=chunk_id,
                    metadata=metadata,
                    start_idx=i,
                    end_idx=min(i + chunk_size, len(words))
                ))
        
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
        batch_size = 32
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            embeddings.append(batch_embeddings)
        
        embeddings = np.vstack(embeddings).astype('float32')
        
        # 保存嵌入到chunks
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i]
        
        # 创建FAISS索引
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # 使用内积（余弦相似度）
        
        # 归一化并添加到索引
        faiss.normalize_L2(embeddings)
        self.index.add(embeddings)
        
        self.chunks = chunks
        print(f"[RAG] Index built with dimension {self.embedding_dim}")
    
    def search(self, query: str, top_k: int = 10, 
              threshold: float = 0.0) -> List[TextChunk]:
        """
        搜索相关文本块
        
        Args:
            query: 查询字符串
            top_k: 返回结果数
            threshold: 相似度阈值
            
        Returns:
            相关文本块列表
        """
        if not self.index or not self.chunks:
            print("[RAG] No index available")
            return []
        
        # 编码查询
        query_embedding = self.model.encode([query], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # 搜索
        distances, indices = self.index.search(query_embedding, min(top_k, len(self.chunks)))
        
        # 过滤并返回结果
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.chunks) and dist > threshold:
                chunk = self.chunks[idx]
                chunk.score = float(dist)  # 添加相似度分数
                results.append(chunk)
        
        return results
    
    def retrieve_for_dimension(self, entity: Any, dimension_key: str, 
                               dimension_question: str) -> Tuple[List[TextChunk], str]:
        """
        为特定维度检索相关内容
        
        Args:
            entity: 实体对象
            dimension_key: 维度键
            dimension_question: 维度问题
            
        Returns:
            (相关块列表, 格式化的上下文)
        """
        # 构建查询
        query = self._build_dimension_query(entity, dimension_key, dimension_question)
        
        # 搜索相关chunks
        relevant_chunks = self.search(query, top_k=15) 
        # 如果第一次检索结果不足，尝试扩展查询
        if len(relevant_chunks) < 3:
            expanded_query = self._expand_query(entity, dimension_key)
            additional_chunks = self.search(expanded_query, top_k=5)
            
            # 合并并去重
            seen_ids = {c.chunk_id for c in relevant_chunks}
            for chunk in additional_chunks:
                if chunk.chunk_id not in seen_ids:
                    relevant_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)
        
        relevant_chunks = self._deduplicate_by_pmid(relevant_chunks)
        # 格式化上下文

        formatted_context = self._format_context(relevant_chunks)
        
        return relevant_chunks, formatted_context
    
    def _deduplicate_by_pmid(self, chunks):
        """新增：按PMID去重"""
        seen_pmids = set()
        unique_chunks = []
        
        for chunk in chunks:
            pmid = getattr(chunk, 'doc_id', None)
            if pmid:
                if pmid not in seen_pmids:
                    unique_chunks.append(chunk)
                    seen_pmids.add(pmid)
            else:
                unique_chunks.append(chunk)
        
        return unique_chunks
    def _build_dimension_query(self, entity: Any, dimension_key: str, 
                               dimension_question: str) -> str:
        """构建维度特定的查询"""
        
        # 基础实体词汇
        base_terms = []
        if entity.disease:
            base_terms.append(entity.disease)
        if entity.target:
            base_terms.append(entity.target)
        if entity.therapy:
            base_terms.append(entity.therapy)
        if entity.drug:
            base_terms.append(entity.drug)
        
        # 维度特定关键词
        dimension_keywords = {
            'gene_disease_association': ['association', 'GWAS', 'genetic', 'risk', 'variant'],
            'gene_mechanism': ['mechanism', 'pathway', 'signaling', 'function', 'regulation'],
            'gene_druggability': ['drug target', 'inhibitor', 'therapeutic', 'druggable', 'binding'],
            'disease_pathogenesis': ['pathogenesis', 'etiology', 'pathophysiology', 'mechanism'],
            'disease_treatment_landscape': ['treatment', 'therapy', 'clinical', 'guideline', 'management'],
            'disease_targets': ['therapeutic target', 'drug target', 'biomarker', 'pathway'],
            'gene_disease_mechanism': ['mechanism', 'role', 'function', 'pathogenesis', 'pathway'],
            'gene_disease_therapy': ['treatment', 'therapy', 'clinical trial', 'efficacy', 'drug'],
            'therapy_mechanism': ['mechanism of action', 'MOA', 'target', 'pathway', 'pharmacology'],
            'therapy_efficacy': ['efficacy', 'clinical trial', 'outcome', 'safety', 'response'],
            'drug_mechanism': ['mechanism', 'target', 'pharmacology', 'binding', 'action'],
            'drug_clinical': ['clinical trial', 'phase', 'efficacy', 'safety', 'outcome']
        }
        
        # 组合查询
        query_parts = base_terms.copy()
        
        # 添加维度关键词
        if dimension_key in dimension_keywords:
            query_parts.extend(dimension_keywords[dimension_key][:3])
        
        # 添加问题中的关键词
        question_keywords = self._extract_keywords_from_question(dimension_question)
        query_parts.extend(question_keywords[:2])
        
        return ' '.join(query_parts)
    
    def _expand_query(self, entity: Any, dimension_key: str) -> str:
        """扩展查询以获得更多结果"""
        
        # 使用同义词和相关术语
        expansions = []
        
        if entity.target:
            expansions.extend([entity.target, "gene", "protein", "target"])
        
        if entity.disease:
            # 疾病的常见同义词
            disease_lower = entity.disease.lower()
            if "cancer" in disease_lower:
                expansions.extend(["tumor", "carcinoma", "malignancy", "neoplasm"])
            elif "diabetes" in disease_lower:
                expansions.extend(["T2D", "T1D", "glucose", "insulin"])
            else:
                expansions.append(entity.disease)
        
        if entity.therapy:
            expansions.extend([entity.therapy, "treatment", "therapy"])
        
        if entity.drug:
            expansions.extend([entity.drug, "compound", "inhibitor"])
        
        return ' '.join(expansions)
    
    def _extract_keywords_from_question(self, question: str) -> List[str]:
        """从问题中提取关键词"""
        # 简单的关键词提取
        stop_words = {'什么', '如何', '哪些', '是', '的', '吗', '呢', '了', '着', 
                     'what', 'how', 'which', 'is', 'are', 'the', 'a', 'an'}
        
        words = question.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords[:5]
    
    def _format_context(self, chunks: List[TextChunk]) -> str:
        """格式化上下文"""
        if not chunks:
            return ""
        
        # 按相关性排序（如果有分数）
        if hasattr(chunks[0], 'score'):
            chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        
        # 格式化每个块
        formatted_parts = []
        seen_pmids = set()
        
        for i, chunk in enumerate(chunks, 1):
            # 添加文献标识
            ref_marker = f"[REF{i}]"
            
            # 格式化文本
            formatted_text = f"{ref_marker} {chunk.text}"
            
            # 添加元数据（仅首次出现的PMID）
            if chunk.doc_id not in seen_pmids:
                metadata = f"\n来源: {chunk.metadata.get('title', 'Unknown')[:100]}... " \
                          f"({chunk.metadata.get('journal', 'Unknown')}, {chunk.metadata.get('year', 'Unknown')})"
                formatted_text += metadata
                seen_pmids.add(chunk.doc_id)
            
            formatted_parts.append(formatted_text)
        
        # 组合
        context = "\n\n".join(formatted_parts)
        
        # 添加参考文献列表
        references = self._format_references(chunks)
        
        return f"{context}\n\n{references}"
    
    def _format_references(self, chunks: List[TextChunk]) -> str:
        """格式化参考文献列表"""
        refs = []
        seen_pmids = set()
        
        for chunk in chunks:
            if chunk.doc_id not in seen_pmids:
                seen_pmids.add(chunk.doc_id)
                title = chunk.metadata.get('title', 'Unknown Title')
                if len(title) > 100:
                    title = title[:100] + "..."
                
                refs.append(
                    f"[PMID:{chunk.doc_id}] {title} "
                    f"({chunk.metadata.get('journal', 'Unknown Journal')}, "
                    f"{chunk.metadata.get('year', 'Unknown Year')})"
                )
        
        if refs:
            return "参考文献：\n" + "\n".join(refs[:10])  # 最多10篇
        return ""
    
    def _get_cache_key(self, articles: List[Any]) -> str:
        """生成缓存键"""
        # 使用文章ID生成唯一键
        pmids = sorted([a.pmid for a in articles])
        key_str = "_".join(pmids[:10])  # 使用前10个PMID
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
    
    def clear_cache(self):
        """清空缓存"""
        import shutil
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
        print("[RAG] Cache cleared")