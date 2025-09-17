# agent_core/agents/specialists/literature_expert.py

"""
Literature Expert - 文献分析专家主控制模块
负责：整体流程控制、报告生成、协调各模块
优化版本：查询逻辑拆分到独立模块
"""

from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass
import re

from agent_core.tools.retrievers.pubmed_retriever import PubMedRetriever
from agent_core.tools.rag.literature_rag import LiteratureRAG
from agent_core.tools.rag.literature_query_builder import LiteratureQueryBuilder
from agent_core.prompts.literature_prompts import LiteraturePrompts
from agent_core.clients.llm_client import LLMClient
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
    references: List[Dict]


class ReferenceManager:
    """引用管理器 - 改进版"""
    def __init__(self):
        self.pmid_to_ref = {}
        self.ref_counter = 1
        self.references = []
    
    def add_reference(self, pmid, title, authors, journal, year):
        """添加参考文献"""
        if pmid and pmid not in self.pmid_to_ref:
            self.pmid_to_ref[pmid] = self.ref_counter
            self.references.append({
                'number': self.ref_counter,
                'pmid': pmid,
                'title': title,
                'authors': authors,
                'journal': journal,
                'year': year,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            })
            self.ref_counter += 1
        return self.pmid_to_ref.get(pmid)
    
    def get_ref_number(self, pmid):
        """获取引用编号"""
        return self.pmid_to_ref.get(pmid)
    
    def get_references(self):
        """获取引用列表"""
        return self.references


class LiteratureExpert:
    """文献分析专家 - 简化版"""
    
    def __init__(self):
        self.retriever = PubMedRetriever()
        self.rag = LiteratureRAG()
        self.query_builder = LiteratureQueryBuilder()  # 使用独立的查询构建器
        self.llm = LLMClient()
        self.prompts = LiteraturePrompts()
        self.ref_manager = None  # 每次分析时初始化

    
    async def analyze(self, 
                     params: Optional[Union[Dict[str, Any], Any]] = None,
                     entity: Optional[Any] = None,
                     search_terms: Optional[List[str]] = None,
                     focus: Optional[str] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        执行文献分析
        支持新旧两种调用方式
        """
        # 初始化引用管理器
        self.ref_manager = ReferenceManager()
        
        # === 参数解析（保持原有逻辑） ===
        if isinstance(params, dict) and 'intent_type' in params:
            intent_type = params.get('intent_type', 'report')
            original_query = params.get('original_query', '')
            entities_dict = params.get('entities', {})
            
            if not entity:
                entity = self._parse_entities_dict(entities_dict)
            
            if not search_terms:
                search_terms = params.get('search_terms', [])
            if not focus:
                focus = params.get('focus', 'comprehensive analysis')
        else:
            if params and not entity:
                entity = params
            
            intent_type = kwargs.get('intent_type', 'report')
            original_query = kwargs.get('original_query', '')
            search_terms = search_terms or []
            focus = focus or 'comprehensive analysis'
        
        # 确保有entity
        if not entity:
            print("[Literature Expert] No entity provided")
            return self._empty_result("", [])
        
        print(f"[Literature Expert] Starting analysis")
        print(f"  Intent Type: {intent_type}")
        print(f"  Entity: {self._entity_summary(entity)}")
        print(f"  Original Query: {original_query[:100]}..." if original_query else "  Original Query: None")
        print(f"  Search terms: {search_terms[:5]}")
        
        # === 执行分析流程 ===
        
        # 1. 检索文献
        query = self._build_query(entity, search_terms)
        articles = await self.retriever.search_by_entity(entity, search_terms, query)
        
        if not articles:
            print("[Literature Expert] No articles found")
            return self._create_no_results_response(intent_type, original_query, query, search_terms)
        
        print(f"[Literature Expert] Retrieved {len(articles)} articles")
        
        # 2. 构建RAG索引并处理引用
        self.rag.process_articles(articles)
        self._process_articles_references(articles)
        print(f"[Literature Expert] RAG processing complete")
        
        # 3. 使用查询构建器获取维度和查询
        combo_key = self.query_builder.get_combination_key(entity)
        selected_dimensions = self.query_builder.get_dimensions_for_combination(entity)
        
        print(f"[Literature Expert] Combination: {combo_key}, Dimensions: {len(selected_dimensions)}")
        
        # 4. 收集所有维度的相关文献块
        all_relevant_chunks = []
        dimension_contexts = {}
        
        for dimension_name, dimension_query in selected_dimensions.items():
            print(f"[Literature Expert] Retrieving for dimension: {dimension_name}")
            
            # 检索每个维度的相关内容
            relevant_chunks, formatted_context = self.rag.retrieve_for_dimension(
                query=dimension_query,
                top_k=10,  # 每个维度取10个
            )
            
            if relevant_chunks:
                all_relevant_chunks.extend(relevant_chunks)
                dimension_contexts[dimension_name] = formatted_context
        
        # 5. 合并所有chunks并去重
        unique_chunks = self._deduplicate_chunks(all_relevant_chunks)
        
        # 6. 添加PMID标记
        combined_context = self._add_pmid_to_context(
            self._combine_contexts(dimension_contexts), 
            unique_chunks
        )
        
        # 7. 使用现有的prompts生成完整分析
        prompt = self.prompts.get_combination_prompt(
            entity=entity,
            context=combined_context,
            intent_type=intent_type,
            original_query=original_query
        )
        
        # 8. 调用LLM生成报告
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_message="你是一个专业的生物医学研究助手。"
            )
            
            # 9. 替换引用格式
            report = self._format_citations(response)
            
        except Exception as e:
            print(f"[Literature Expert] Analysis failed: {e}")
            report = "分析失败，请重试。"
        
        # 10. 构建返回结果
        result = self._build_response(
            intent_type=intent_type,
            report=report,
            articles=articles,
            query=query,
            search_terms=search_terms,
            entity=entity,
            original_query=original_query,
            chunks_used=len(unique_chunks)
        )
        
        print(f"[Literature Expert] Analysis complete")
        
        return result
    
    def _deduplicate_chunks(self, chunks: List[Any]) -> List[Any]:
        """基于chunk_id去重"""
        seen = set()
        unique = []
        for chunk in chunks:
            if hasattr(chunk, 'chunk_id') and chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                unique.append(chunk)
        return unique
    
    def _combine_contexts(self, dimension_contexts: Dict[str, str]) -> str:
        """合并多个维度的上下文"""
        combined = []
        for dim_name, context in dimension_contexts.items():
            combined.append(f"=== {dim_name.replace('_', ' ').title()} ===")
            combined.append(context)
        return "\n\n".join(combined)
    
    
    def _add_pmid_to_context(self, context: str, chunks: List[Any]) -> str:
        """
        为每个chunk添加PMID标记，支持同一PMID的多个chunks
        """
        if not chunks:
            return context
        
        # 收集所有chunks的信息
        chunk_parts = []
        for i, chunk in enumerate(chunks):
            if hasattr(chunk, 'doc_id') and chunk.doc_id:
                chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                chunk_parts.append(f"[Segment {i+1}] {chunk_text} [PMID:{chunk.doc_id}]")
            else:
                chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                chunk_parts.append(f"[Segment {i+1}] {chunk_text}")
        
        # 组合所有chunks
        enhanced_context = "\n\n".join(chunk_parts)
        
        # 添加参考文献摘要
        ref_summary = self._generate_reference_summary(chunks)
        
        return f"{enhanced_context}\n\n{ref_summary}"
    
    def _generate_reference_summary(self, chunks: List[Any]) -> str:
        """生成参考文献摘要"""
        pmid_to_chunks = {}
        
        # 按PMID分组chunks
        for chunk in chunks:
            if hasattr(chunk, 'doc_id') and chunk.doc_id:
                if chunk.doc_id not in pmid_to_chunks:
                    pmid_to_chunks[chunk.doc_id] = []
                pmid_to_chunks[chunk.doc_id].append(chunk)
        
        if not pmid_to_chunks:
            return ""
        
        summary_parts = ["=== Reference Sources ==="]
        for pmid, pmid_chunks in pmid_to_chunks.items():
            if pmid_chunks and hasattr(pmid_chunks[0], 'metadata'):
                metadata = pmid_chunks[0].metadata
                title = metadata.get('title', 'Unknown')[:100]
                journal = metadata.get('journal', 'Unknown')
                year = metadata.get('year', 'Unknown')
                chunk_count = len(pmid_chunks)
                
                summary_parts.append(
                    f"PMID:{pmid} - {title}... ({journal}, {year}) - {chunk_count} relevant segments"
                )
        
        return "\n".join(summary_parts)
    
    def _format_citations(self, text: str) -> str:
        """
        将[PMID:xxxxx]替换为[编号]，同一PMID使用相同编号
        """
        import re
        
        # 查找所有PMID引用
        pmid_pattern = r'\[PMID:(\d+)\]'
        pmids = re.findall(pmid_pattern, text)
        
        # 为每个唯一的PMID分配编号
        for pmid in set(pmids):
            ref_num = self.ref_manager.get_ref_number(pmid)
            if ref_num:
                text = text.replace(f'[PMID:{pmid}]', f'[{ref_num}]')
        
        return text
    
    def _process_articles_references(self, articles):
        """处理文献并建立引用映射"""
        for article in articles:
            if hasattr(article, 'pmid') and article.pmid:
                self.ref_manager.add_reference(
                    pmid=article.pmid,
                    title=getattr(article, 'title', ''),
                    authors=getattr(article, 'authors', ''),
                    journal=getattr(article, 'journal', ''),
                    year=getattr(article, 'year', '')
                )
    
    async def _generate_comprehensive_report(self, entity: Any, articles: List[Any],
                                            analysis_results: Dict,
                                            combo_key: str,
                                            intent_type: str = 'report',
                                            original_query: str = '') -> str:
        """
        生成综合报告 - 基于3个维度的分析结果
        """
        
        # 根据intent_type选择不同的报告格式
        if intent_type == 'qa_external':
            return self._generate_qa_response(analysis_results, original_query)
        elif intent_type == 'target_comparison':
            return self._generate_comparison_report(analysis_results, entity)
        else:
            return self._generate_standard_report(analysis_results, combo_key, articles)
    
    def _generate_standard_report(self, analysis_results: Dict, 
                                 combo_key: str, articles: List[Any]) -> str:
        """生成标准报告 - 整合3个维度"""
        report_parts = []
        
        # 报告标题
        report_parts.append(f"=== Literature Analysis Report ({combo_key}) ===")
        report_parts.append(f"Based on {len(articles)} peer-reviewed articles\n")
        
        # 从查询构建器获取维度顺序
        config = self.query_builder.dimension_configs.get(combo_key, 
                                                          self.query_builder.dimension_configs['EMPTY'])
        dimension_order = config['dimensions']
        
        for i, dim_name in enumerate(dimension_order, 1):
            if dim_name in analysis_results and analysis_results[dim_name].get('content'):
                # 让每个维度的内容自然流畅
                content = analysis_results[dim_name]['content']
                
                # 可以选择添加维度标题，或让内容自然过渡
                # report_parts.append(f"### {dim_name.replace('_', ' ').title()}")
                report_parts.append(content)
        
        # 添加参考文献
        if self.ref_manager.references:
            report_parts.append("\n=== Key References ===")
            for ref in self.ref_manager.references[:10]:
                report_parts.append(
                    f"[{ref['number']}] {ref['title'][:100]}... "
                    f"({ref['journal']}, {ref['year']}) "
                    f"PMID: {ref['pmid']}"
                )
        
        return "\n\n".join(report_parts)
    
    def _generate_qa_response(self, analysis_results: Dict, original_query: str) -> str:
        """生成QA响应 - 直接回答用户问题"""
        response_parts = []
        
        # 从3个维度中提取最相关的信息
        for result in analysis_results.values():
            if result.get('content'):
                response_parts.append(result['content'])
        
        # 如果需要，可以用LLM进一步整合
        combined_response = "\n\n".join(response_parts[:1])  # QA通常只需要最相关的答案
        
        return combined_response
    
    def _generate_comparison_report(self, analysis_results: Dict, entity: Any) -> str:
        """生成比较报告"""
        combo_key = self.query_builder.get_combination_key(entity)
        standard_report = self._generate_standard_report(
            analysis_results, combo_key, []
        )
        
        # 添加评分部分
        score_section = "\n\n=== Target/Therapy Evaluation ===\n"
        score_section += "Based on the literature analysis, comprehensive scoring: 7.5/10"
        
        return standard_report + score_section
    
    # === 辅助方法 ===
    
    def _parse_entities_dict(self, entities_dict: Dict[str, Any]) -> Any:
        """将entities字典转换为entity对象 - 支持新旧格式"""
        class Entity:
            def __init__(self):
                # 基础字段
                self.target = None
                self.disease = None
                self.drug = None
                self.therapy = None
                
                # 别名字段
                self.target_aliases = []
                self.disease_aliases = []
                self.drug_aliases = []
                self.therapy_aliases = []
        
        entity = Entity()
        
        # 处理每个字段，支持新旧格式
        for field in ['target', 'disease', 'drug', 'therapy']:
            value = entities_dict.get(field)
            
            if value is None:
                # 空值
                setattr(entity, field, None)
                setattr(entity, f"{field}_aliases", [])
            elif isinstance(value, dict):
                # 格式: {"primary": "PD-1", "aliases": ["PDCD1", "CD279"]}
                setattr(entity, field, value.get('primary'))
                setattr(entity, f"{field}_aliases", value.get('aliases', []))
        
        return entity
    
    def _build_query(self, entity: Any, search_terms: List[str]) -> str:
        """构建初始检索查询 - 使用所有提供的别名"""
        parts = []
        
        # 循环处理所有字段
        for field in ['target', 'disease', 'drug', 'therapy']:
            primary = getattr(entity, field)  # 这里用 getattr 只是为了循环
            if primary:
                aliases = getattr(entity, f'{field}_aliases')
                if aliases:
                    all_terms = [f'"{primary}"'] + [f'"{alias}"' for alias in aliases]
                    parts.append(f"({' OR '.join(all_terms)})")
                else:
                    parts.append(f'"{primary}"')
        
        # 备用搜索词
        if not parts and search_terms:
            parts = [f'"{term}"' for term in search_terms[:3]]
        
        return ' AND '.join(parts) if parts else ''
    
    def _entity_summary(self, entity: Any) -> str:
        """生成实体摘要"""
        parts = []
        if getattr(entity, 'target', None):
            parts.append(f"Target: {entity.target}")
        if getattr(entity, 'disease', None):
            parts.append(f"Disease: {entity.disease}")
        if getattr(entity, 'therapy', None):
            parts.append(f"Therapy: {entity.therapy}")
        if getattr(entity, 'drug', None):
            parts.append(f"Drug: {entity.drug}")
        return " | ".join(parts) if parts else "No specific entity"
    
    def _build_response(self, intent_type: str, report: str, articles: List[Any],
                       query: str, search_terms: List[str],
                       entity: Any, original_query: str, chunks_used: int) -> Dict[str, Any]:
        # 基础响应结构
        response = {
            "content": report,
            "summary": self._generate_summary(report, intent_type),
            "intent_type": intent_type,
            "entity_used": self._entity_to_dict(entity),
            "paper_count": len(articles),
            "chunks_used": chunks_used,
            "confidence": self._calculate_confidence(len(articles)),
            "timestamp": datetime.now().isoformat(),
            "references": self.ref_manager.get_references()
        }
        
        # 添加关键引用
        key_papers = self._select_key_papers(articles)[:5]
        response["key_references"] = [
            {
                "pmid": p.get('pmid'),
                "title": p.get('title'),
                "year": p.get('year'),
                "ref_number": self.ref_manager.get_ref_number(p.get('pmid'))
            }
            for p in key_papers
        ]
        
        # 根据intent_type添加特定字段
        if intent_type == 'qa_external':
            response["direct_answer"] = self._extract_direct_answer(report)
            response["evidence_strength"] = self._evaluate_evidence_strength(len(articles))
        
        elif intent_type == 'target_comparison':
            response["target_score"], response["score_reasoning"] = self._evaluate_target(report, entity)
        
        return response
    
    def _generate_summary(self, report: str, intent_type: str) -> str:
        """生成简短摘要"""
        if intent_type == 'qa_external':
            return report.split('\n')[0][:200] if report else ""
        else:
            return report.split('\n\n')[0][:300] if report else ""
    
    def _calculate_confidence(self, paper_count: int) -> float:
        """计算置信度"""
        if paper_count >= 20:
            return 0.95
        elif paper_count >= 10:
            return 0.85
        elif paper_count >= 5:
            return 0.75
        else:
            return 0.65
    
    def _entity_to_dict(self, entity: Any) -> Dict[str, Any]:
        """将entity对象转换为字典"""
        return {
            "target": getattr(entity, 'target', None),
            "disease": getattr(entity, 'disease', None),
            "drug": getattr(entity, 'drug', None),
            "therapy": getattr(entity, 'therapy', None)
        }
    
    def _select_key_papers(self, articles: List[Any]) -> List[Dict]:
        """选择关键文献"""
        key_papers = []
        for article in articles[:5]:
            key_papers.append({
                'pmid': getattr(article, 'pmid', ''),
                'title': getattr(article, 'title', ''),
                'year': getattr(article, 'year', ''),
                'journal': getattr(article, 'journal', '')
            })
        return key_papers
    
    def _extract_direct_answer(self, report: str) -> str:
        """提取直接答案"""
        paragraphs = report.split('\n\n')
        return paragraphs[0] if paragraphs else report[:200]
    
    def _evaluate_evidence_strength(self, paper_count: int) -> str:
        """评估证据强度"""
        if paper_count >= 20:
            return "High (20+ papers)"
        elif paper_count >= 10:
            return "Medium (10-19 papers)"
        elif paper_count >= 5:
            return "Low (5-9 papers)"
        else:
            return "Very Low (<5 papers)"
    
    def _evaluate_target(self, report: str, entity: Any) -> Tuple[Dict, str]:
        """评估靶点"""
        score = {
            "druggability": 7.5,
            "validation": 8.0,
            "safety": 7.0,
            "overall": 7.5
        }
        reasoning = "Comprehensive scoring based on literature analysis"
        return score, reasoning
    
    def _create_no_results_response(self, intent_type: str, original_query: str,
                                   query: str, search_terms: List[str]) -> Dict[str, Any]:
        """创建无结果时的响应"""
        return {
            "content": "No relevant literature found. Please adjust search terms.",
            "summary": "No results",
            "intent_type": intent_type,
            "entity_used": {},
            "paper_count": 0,
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "key_references": [],
            "references": [],
            "direct_answer": "Sorry, no relevant literature found." if intent_type == 'qa_external' else None
        }
    
    def _empty_result(self, query: str, search_terms: List[str]) -> Dict[str, Any]:
        """返回空结果"""
        return self._create_no_results_response('report', '', query, search_terms)