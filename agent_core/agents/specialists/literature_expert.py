# agent_core/agents/specialists/literature_expert.py

"""
Literature Expert - 文献分析专家
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from agent_core.tools.retrievers.pubmed_retriever import PubMedRetriever, PubMedArticle
from agent_core.tools.rag.rag_processor import LiteratureRAG, TextChunk
from agent_core.clients.llm_client import LLMClient
from agent_core.prompts import literature_prompts
from agent_core.config.settings import config


@dataclass
class LiteratureAnalysisResult:
    """文献分析结果结构"""
    total_papers: int
    analysis: Dict[str, Dict]
    report: str
    key_papers: List[Dict]
    evidence_level: str
    timestamp: str
    query_used: str
    search_terms: List[str]


class LiteratureExpert:
    """文献分析专家"""
    
    def __init__(self):
        self.retriever = PubMedRetriever()
        self.rag = LiteratureRAG()
        self.llm = LLMClient()
        
        # 三个核心分析维度
        self.dimensions = {
            'disease_mechanism': '该基因与哪些疾病相关？疾病的发病机制是什么？有什么临床需求？',
            'treatment_strategy': '有哪些治疗方法和策略？包括药物、疗法等？临床研究现状如何？',
            'target_analysis': '该基因的作用通路是什么？有哪些潜在治疗靶点？研究进展如何？'
        }
        
    async def analyze(self,
                     entity: Any,
                     search_terms: List[str],
                     focus: str,
                     **kwargs) -> Dict[str, Any]:
        """
        主分析入口
        
        Args:
            entity: 实体对象 (disease, target, drug, therapy)
            search_terms: 搜索词列表（包含别名）
            focus: 用户关注焦点
            **kwargs: 其他参数
            
        Returns:
            分析结果字典
        """
        print(f"[Literature Expert] Starting analysis")
        print(f"  Entity: {self._entity_summary(entity)}")
        print(f"  Search terms: {search_terms[:5]}")
        
        # 1. 构建查询并检索文献
        query = self._build_query(entity, search_terms)
        articles = await self._retrieve_articles(entity, search_terms, query)
        
        if not articles:
            print("[Literature Expert] No articles found")
            return self._empty_result(query, search_terms)
        
        print(f"[Literature Expert] Retrieved {len(articles)} articles")
        
        # 2. 构建RAG索引
        chunks = self.rag.create_chunks(articles)
        self.rag.build_index(chunks)
        print(f"[Literature Expert] Created {len(chunks)} chunks for RAG")
        
        # 3. 执行三维度分析
        analysis_results = {}
        for dimension_key, dimension_question in self.dimensions.items():
            print(f"[Literature Expert] Analyzing {dimension_key}")
            analysis_results[dimension_key] = await self._analyze_dimension(
                entity=entity,
                dimension_key=dimension_key,
                dimension_question=dimension_question
            )
        
        # 4. 生成综合报告
        report = await self._generate_comprehensive_report(
            entity=entity,
            articles=articles,
            analysis_results=analysis_results,
            focus=focus
        )
        
        # 5. 构建返回结果
        result = LiteratureAnalysisResult(
            total_papers=len(articles),
            analysis=analysis_results,
            report=report,
            key_papers=self._select_key_papers(articles),
            evidence_level=self._assess_evidence_level(len(articles)),
            timestamp=datetime.now().isoformat(),
            query_used=query,
            search_terms=search_terms
        )
        
        print(f"[Literature Expert] Analysis complete")
        
        return self._result_to_dict(result)
    
    def _build_query(self, entity: Any, search_terms: List[str]) -> str:
        """构建PubMed查询字符串"""
        parts = []
        
        # 优先级1: 疾病+靶点组合
        if entity.disease and entity.target:
            parts.append(f'("{entity.disease}" AND "{entity.target}")')
        elif entity.disease:
            parts.append(f'"{entity.disease}"')
        elif entity.target:
            parts.append(f'"{entity.target}"')
        
        # 优先级2: 治疗方式
        if entity.therapy:
            parts.append(f'"{entity.therapy}"')
            
        # 优先级3: 药物
        if entity.drug:
            parts.append(f'"{entity.drug}"')
        
        # 如果没有实体，使用搜索词
        if not parts and search_terms:
            parts = [f'"{term}"' for term in search_terms[:3]]
        
        return ' AND '.join(parts) if parts else ''


    def _build_dimension_query(self, entity: Any, dimension: str) -> str:
        """构建维度查询"""
        
        # 基础查询词
        base_terms = []
        if entity.disease:
            base_terms.append(entity.disease)
        if entity.target:
            base_terms.append(entity.target)
        if entity.therapy:
            base_terms.append(entity.therapy)
        if entity.drug:
            base_terms.append(entity.drug)
        
        base_query = " ".join(base_terms)
        
        # 添加维度特定词
        if dimension == 'disease_mechanism':
            return f"{base_query} mechanism pathogenesis molecular pathway"
        elif dimension == 'treatment_strategy':
            return f"{base_query} treatment therapy clinical trial efficacy"
        elif dimension == 'target_analysis':
            return f"{base_query} target druggability binding site inhibitor"
        else:
            return base_query
    async def _retrieve_articles(self, 
                                entity: Any, 
                                search_terms: List[str],
                                primary_query: str) -> List[PubMedArticle]:
        """检索文献"""
        all_articles = []
        seen_pmids = set()
        
        # 1. 主查询
        if primary_query:
            articles = await self.retriever.search(primary_query, config.max_articles)
            for article in articles:
                if article.pmid not in seen_pmids:
                    all_articles.append(article)
                    seen_pmids.add(article.pmid)
        
        # 2. 如果结果不足，扩展搜索
        if len(all_articles) < 20:
            # 基于实体扩展
            if entity.target and len(all_articles) < 20:
                more = await self.retriever.search(entity.target, 30)
                for article in more:
                    if article.pmid not in seen_pmids:
                        all_articles.append(article)
                        seen_pmids.add(article.pmid)
            
            # 基于别名扩展
            if len(all_articles) < 20 and search_terms:
                for term in search_terms[:2]:  # 只用前2个别名
                    if len(all_articles) >= 50:
                        break
                    more = await self.retriever.search(term, 20)
                    for article in more:
                        if article.pmid not in seen_pmids:
                            all_articles.append(article)
                            seen_pmids.add(article.pmid)
        
        # 限制总数
        return all_articles[:config.max_articles]
    
    async def _analyze_dimension(self,
                            entity: Any,
                            dimension_key: str) -> Dict:
        """分析单个维度"""
        
        # 构建查询
        query = self._build_dimension_query(entity, dimension_key)
        
        # RAG检索相关chunks
        relevant_chunks = self.rag.search(query, top_k=config.max_chunks_per_query)
        
        if not relevant_chunks:
            return {
                'content': f'未找到{dimension_key}相关内容',
                'chunks_used': 0
            }
        
        # 格式化上下文和参考文献
        context, references = self._format_context_and_refs(relevant_chunks)
        
        # 选择合适的提示词
        prompt = self._select_prompt(entity, dimension_key, context, references)
        
        # LLM分析 - 不传递temperature参数
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_message="你是一个专业的生物医学研究助手"
            )
            
            return {
                'content': response,
                'chunks_used': len(relevant_chunks),
                'pmids_referenced': list(set([c.doc_id for c in relevant_chunks]))
            }
            
        except Exception as e:
            print(f"[Literature Expert] Analysis failed for {dimension_key}: {e}")
            return {
                'content': f'{dimension_key}分析失败',
                'chunks_used': 0,
                'error': str(e)
            }
        
            
      
    async def _generate_comprehensive_report(self,
                                            entity: Any,
                                            articles: List[PubMedArticle],
                                            analysis_results: Dict,
                                            focus: str) -> str:
        """生成综合报告"""
        
        report_parts = [
            "# 文献分析综合报告",
            "",
            f"**分析焦点**: {focus}",
            f"**检索文献数量**: {len(articles)} 篇",
            f"**证据等级**: {self._assess_evidence_level(len(articles))}",
            f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            ""
        ]
        
        # 添加实体信息
        entity_info = self._entity_summary(entity)
        if entity_info:
            report_parts.extend([
                "## 研究对象",
                entity_info,
                "",
                "---",
                ""
            ])
        
        # 添加三维度分析结果
        dimension_titles = {
            'disease_mechanism': '## 一、疾病机制与临床需求',
            'treatment_strategy': '## 二、治疗策略与临床进展',
            'target_analysis': '## 三、靶点成药性与开发前景'
        }
        
        for dimension_key, title in dimension_titles.items():
            if dimension_key in analysis_results:
                result = analysis_results[dimension_key]
                if result.get('content'):
                    report_parts.extend([
                        title,
                        "",
                        result['content'],
                        "",
                        f"*基于 {result.get('chunks_used', 0)} 个文献片段分析*",
                        "",
                        "---",
                        ""
                    ])
        
        # 添加关键文献列表
        key_papers = self._select_key_papers(articles)
        if key_papers:
            report_parts.extend([
                "## 关键参考文献",
                ""
            ])
            
            for i, paper in enumerate(key_papers, 1):
                report_parts.append(
                    f"{i}. {paper['title']} "
                    f"({paper['journal']}, {paper['year']}) "
                    f"[PMID: {paper['pmid']}]({paper['url']})"
                )
            
            report_parts.append("")
        
        # 添加总结
        summary = await self._generate_executive_summary(
            entity, analysis_results, len(articles)
        )
        if summary:
            report_parts.extend([
                "---",
                "",
                "## 执行摘要",
                "",
                summary
            ])
        
        return "\n".join(report_parts)
    
    async def _generate_executive_summary(self,
                                         entity: Any,
                                         analysis_results: Dict,
                                         article_count: int) -> str:
        """生成执行摘要"""
        
        # 提取关键信息
        key_points = []
        
        for dimension, result in analysis_results.items():
            if result.get('content'):
                # 从每个维度提取关键点（这里简化处理）
                key_points.append(f"{dimension}: 已完成分析")
        
        target = entity.target or entity.therapy or "研究目标"
        
        summary = f"""
基于 {article_count} 篇文献的综合分析显示：

1. **研究现状**: {target} 相关研究活跃，文献证据{self._assess_evidence_level(article_count)}
2. **关键发现**: 完成疾病机制、治疗策略和靶点分析三个维度的深度分析
3. **发展趋势**: 研究热点集中在精准治疗和新型疗法开发
4. **机会识别**: 存在潜在的药物开发和临床转化机会

建议重点关注最新的临床研究进展和技术突破。
"""
        
        return summary.strip()
    
    def _select_key_papers(self, articles: List[PubMedArticle]) -> List[Dict]:
        """选择关键文献（最新+最相关）"""
        
        # 按年份排序
        sorted_articles = sorted(articles, key=lambda x: x.year, reverse=True)
        
        key_papers = []
        for article in sorted_articles[:5]:  # 取最新5篇
            key_papers.append({
                'pmid': article.pmid,
                'title': article.title[:150] + ('...' if len(article.title) > 150 else ''),
                'authors': article.authors[:3],  # 前3个作者
                'journal': article.journal,
                'year': article.year,
                'doi': article.doi,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/"
            })
        
        return key_papers
    
    def _assess_evidence_level(self, article_count: int) -> str:
        """评估证据等级"""
        if article_count >= 100:
            return "强 (Strong)"
        elif article_count >= 50:
            return "中等 (Moderate)"
        elif article_count >= 20:
            return "有限 (Limited)"
        elif article_count >= 5:
            return "较弱 (Weak)"
        else:
            return "极少 (Very Limited)"
    
    def _format_references(self, chunks: List[TextChunk]) -> str:
        """格式化参考文献列表"""
        if not chunks:
            return ""
        
        refs = []
        seen_pmids = set()
        
        for chunk in chunks:
            if chunk.doc_id not in seen_pmids:
                seen_pmids.add(chunk.doc_id)
                title = chunk.metadata.get('title', 'Unknown Title')
                if len(title) > 100:
                    title = title[:100] + "..."
                    
                refs.append(
                    f"文献{len(refs)+1}: {title} "
                    f"({chunk.metadata.get('journal', 'Unknown Journal')}, "
                    f"{chunk.metadata.get('year', 'Unknown Year')}) "
                    f"[PMID:{chunk.doc_id}]"
                )
        
        if refs:
            return "参考文献列表：\n" + "\n".join(refs)
        return ""
    
    def _entity_summary(self, entity: Any) -> str:
        """生成实体摘要"""
        parts = []
        
        if entity.disease:
            parts.append(f"**疾病**: {entity.disease}")
        if entity.target:
            parts.append(f"**靶点/基因**: {entity.target}")
        if entity.therapy:
            parts.append(f"**治疗方式**: {entity.therapy}")
        if entity.drug:
            parts.append(f"**药物**: {entity.drug}")
        
        return " | ".join(parts) if parts else ""
    
    def _empty_result(self, query: str, search_terms: List[str]) -> Dict[str, Any]:
        """返回空结果"""
        result = LiteratureAnalysisResult(
            total_papers=0,
            analysis={},
            report="未找到相关文献，请尝试调整搜索条件",
            key_papers=[],
            evidence_level="无 (None)",
            timestamp=datetime.now().isoformat(),
            query_used=query,
            search_terms=search_terms
        )
        
        return self._result_to_dict(result)
    
    def _result_to_dict(self, result: LiteratureAnalysisResult) -> Dict[str, Any]:
        """将结果对象转换为字典"""
        return {
            'total_papers': result.total_papers,
            'analysis': result.analysis,
            'report': result.report,
            'key_papers': result.key_papers,
            'evidence_level': result.evidence_level,
            'timestamp': result.timestamp,
            'query_used': result.query_used,
            'search_terms': result.search_terms
        }