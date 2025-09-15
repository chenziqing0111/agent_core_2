# agent_core/agents/specialists/literature_expert.py

"""
Literature Expert - 文献分析专家主控制模块
负责：整体流程控制、维度选择、报告生成
优化版本：支持Control Agent的完整参数传入
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass
import re

from agent_core.tools.retrievers.pubmed_retriever import PubMedRetriever
from agent_core.tools.rag.literature_rag import LiteratureRAG
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
    references: List[Dict]  # 添加引用列表


class ReferenceManager:
    """引用管理器"""
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
    
    def get_ref_number(self, pmid):
        """获取引用编号"""
        return self.pmid_to_ref.get(pmid, 0)
    
    def get_reference_list(self):
        """获取引用列表"""
        return sorted(self.references, key=lambda x: x['number'])


class LiteratureExpert:
    """文献分析专家 - 主控制类"""
    
    def __init__(self):
        # 初始化各个模块
        self.retriever = PubMedRetriever()
        self.rag = LiteratureRAG()
        self.prompts = LiteraturePrompts()
        self.llm = LLMClient()
        self.ref_manager = ReferenceManager()
    
    async def analyze(self, 
                     params: Optional[Union[Dict[str, Any], Any]] = None,
                     # 保留旧参数以确保向后兼容
                     entity: Optional[Any] = None,
                     search_terms: Optional[List[str]] = None,
                     focus: Optional[str] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        主分析入口 - 优化版本，支持新旧两种调用方式
        
        新调用方式 (来自Control Agent):
            params = {
                "intent_type": "report/qa_external/target_comparison",
                "original_query": "用户的原始问题",
                "entities": {"target": "PD-1", "disease": "肺癌", ...},
                "search_terms": ["PD-1", "pembrolizumab", ...],  # 可选
                "focus": "用户关注焦点"  # 可选
            }
        
        旧调用方式 (向后兼容):
            直接传入 entity, search_terms, focus
        """
        
        # === 参数解析和兼容性处理 ===
        if params and isinstance(params, dict):
            # 新方式：从params字典解析
            intent_type = params.get('intent_type', 'report')
            original_query = params.get('original_query', '')
            entities_dict = params.get('entities', {})
            
            # 转换entities字典为entity对象
            if not entity:
                entity = self._parse_entities_dict(entities_dict)
            
            # 其他参数
            if not search_terms:
                search_terms = params.get('search_terms', [])
            if not focus:
                focus = params.get('focus', 'comprehensive analysis')
                
        else:
            # 旧方式：使用直接传入的参数或params作为entity
            if params and not entity:
                entity = params  # params可能是entity对象
            
            # 默认值
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
        
        # === 执行分析流程（保持原有逻辑） ===
        
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
        
        # 3. 动态选择分析维度
        selected_dimensions = self._select_dimensions(entity)
        
        # 4. 执行选定维度的分析（传入intent_type和original_query）
        analysis_results = {}
        combo_key = self._get_combination_key(entity)
        
        for dimension_key, dimension_question in selected_dimensions.items():
            print(f"[Literature Expert] Analyzing {dimension_key}")
            analysis_results[dimension_key] = await self._analyze_dimension(
                entity=entity,
                dimension_key=dimension_key,
                dimension_question=dimension_question,
                combo_key=combo_key,
                intent_type=intent_type,  # 新增
                original_query=original_query  # 新增
            )
        
        # 5. 生成综合报告（传入intent_type和original_query）
        report = await self._generate_comprehensive_report(
            entity=entity,
            articles=articles,
            analysis_results=analysis_results,
            selected_dimensions=selected_dimensions,
            focus=focus,
            combo_key=combo_key,
            intent_type=intent_type,  # 新增
            original_query=original_query  # 新增
        )
        
        # 6. 构建返回结果（根据intent_type调整格式）
        result = self._build_response(
            intent_type=intent_type,
            report=report,
            articles=articles,
            analysis_results=analysis_results,
            query=query,
            search_terms=search_terms,
            entity=entity,
            original_query=original_query
        )
        
        print(f"[Literature Expert] Analysis complete")
        
        return result
    
    def _parse_entities_dict(self, entities_dict: Dict[str, Any]) -> Any:
        """将entities字典转换为entity对象"""
        # 创建一个简单的entity对象
        class Entity:
            def __init__(self):
                self.target = None
                self.disease = None
                self.drug = None
                self.therapy = None
        
        entity = Entity()
        entity.target = entities_dict.get('target')
        entity.disease = entities_dict.get('disease')
        entity.drug = entities_dict.get('drug')
        entity.therapy = entities_dict.get('therapy')
        
        return entity
    
    def _build_response(self, intent_type: str, report: str, articles: List[Any],
                       analysis_results: Dict, query: str, search_terms: List[str],
                       entity: Any, original_query: str) -> Dict[str, Any]:
        """根据intent_type构建响应格式"""
        
        # 基础响应结构（轻量级，适配Control Agent的Memory）
        response = {
            "content": report,  # 主要内容
            "summary": self._generate_summary(report, intent_type),  # 简短摘要
            "intent_type": intent_type,
            "entity_used": self._entity_to_dict(entity),
            "paper_count": len(articles),
            "confidence": self._calculate_confidence(len(articles)),
            "timestamp": datetime.now().isoformat()
        }
        
        # 添加关键引用（轻量级，只保留最重要的3-5篇）
        key_papers = self._select_key_papers(articles)[:5]
        response["key_references"] = [
            {
                "pmid": p.get('pmid'),
                "title": p.get('title'),
                "relevance": p.get('relevance', 0.9)
            } for p in key_papers
        ]
        
        # 根据intent_type添加特定字段
        if intent_type == 'target_comparison':
            # 添加靶点评分
            response["target_score"] = self._calculate_target_score(
                entity, analysis_results, articles
            )
            response["score_reasoning"] = self._generate_score_reasoning(
                entity, analysis_results
            )
        
        elif intent_type == 'qa_external':
            # QA模式：添加直接答案
            response["direct_answer"] = self._extract_direct_answer(
                report, original_query
            )
            response["evidence_strength"] = self._assess_evidence_level(len(articles))
        
        return response
    
    def _calculate_target_score(self, entity: Any, analysis_results: Dict, 
                               articles: List[Any]) -> Dict[str, float]:
        """计算靶点评分（用于target_comparison）"""
        # 简单的评分逻辑，可以根据实际需求完善
        score = {
            "therapeutic_potential": min(len(articles) / 10, 3.0),  # 最高3分
            "safety": 1.5,  # 默认1.5分
            "research_maturity": min(len(articles) / 20, 2.0),  # 最高2分
            "clinical_feasibility": 1.5,  # 默认1.5分
            "market_prospect": 0.8,  # 默认0.8分
            "total": 0  # 总分
        }
        score["total"] = sum(v for k, v in score.items() if k != "total")
        return score
    
    def _generate_score_reasoning(self, entity: Any, analysis_results: Dict) -> str:
        """生成评分理由"""
        return f"基于{len(analysis_results)}个维度的分析，该靶点展现出较好的治疗潜力。"
    
    def _extract_direct_answer(self, report: str, original_query: str) -> str:
        """从报告中提取直接答案（用于QA模式）"""
        # 取报告的第一段作为直接答案
        paragraphs = report.split('\n\n')
        for p in paragraphs:
            if len(p.strip()) > 50:  # 找到第一个实质性段落
                return p.strip()[:500]  # 限制长度
        return report[:500]
    
    def _generate_summary(self, report: str, intent_type: str) -> str:
        """生成简短摘要"""
        if intent_type == 'qa_external':
            # QA模式：更简短
            return report.split('\n')[0][:200] if report else ""
        else:
            # Report/Comparison模式：稍长一些
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
    
    def _create_no_results_response(self, intent_type: str, original_query: str,
                                   query: str, search_terms: List[str]) -> Dict[str, Any]:
        """创建无结果时的响应"""
        return {
            "content": "未找到相关文献。建议调整搜索关键词或扩大搜索范围。",
            "summary": "无相关文献",
            "intent_type": intent_type,
            "entity_used": {},
            "paper_count": 0,
            "confidence": 0.0,
            "timestamp": datetime.now().isoformat(),
            "key_references": [],
            "direct_answer": "抱歉，未找到相关文献来回答您的问题。" if intent_type == 'qa_external' else None
        }
    
    # === 以下是需要小幅调整的现有方法 ===
    
    async def _analyze_dimension(self, entity: Any, dimension_key: str, 
                                dimension_question: str, combo_key: str,
                                intent_type: str = 'report',  # 新增参数
                                original_query: str = '') -> Dict:  # 新增参数
        """分析单个维度 - 使用对应组合的prompt"""
        
        # 1. 使用RAG检索相关内容
        relevant_chunks, formatted_context = self.rag.retrieve_for_dimension(
            entity, dimension_key, dimension_question
        )
        
        if not relevant_chunks:
            return {
                'content': f'未找到{dimension_key}相关内容',
                'chunks_used': 0,
                'dimension_question': dimension_question
            }
        
        # 2. 添加PMID标记
        formatted_context = self._add_pmid_to_context(formatted_context, relevant_chunks)
        
        # 3. 使用组合prompt（传入intent_type和original_query）
        prompt = self.prompts.get_combination_prompt(
            entity, 
            formatted_context,
            intent_type=intent_type,  # 新增
            original_query=original_query  # 新增
        )
        
        # 4. 调用LLM进行分析
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_message="你是一个专业的生物医学研究助手。"
            )
            
            # 5. 替换引用格式
            response = self._format_citations(response)
            
            return {
                'content': response,
                'chunks_used': len(relevant_chunks),
                'pmids_referenced': list(set([c.doc_id for c in relevant_chunks if hasattr(c, 'doc_id')])),
                'dimension_question': dimension_question,
                'combination_type': combo_key
            }
            
        except Exception as e:
            print(f"[Literature Expert] Analysis failed for {dimension_key}: {e}")
            return {
                'content': f'{dimension_key}分析失败',
                'chunks_used': 0,
                'error': str(e),
                'dimension_question': dimension_question
            }
    
    async def _generate_comprehensive_report(self, entity: Any, articles: List[Any],
                                            analysis_results: Dict,
                                            selected_dimensions: Dict,
                                            focus: str,
                                            combo_key: str,
                                            intent_type: str = 'report',  # 新增
                                            original_query: str = '') -> str:  # 新增
        """生成综合报告（根据intent_type调整格式）"""
        
        # 根据intent_type选择不同的报告格式
        if intent_type == 'qa_external':
            # QA模式：简洁直接
            return self._generate_qa_response(
                entity, analysis_results, original_query, articles
            )
        elif intent_type == 'target_comparison':
            # 比较模式：完整报告+评分
            return self._generate_comparison_report(
                entity, articles, analysis_results, selected_dimensions, focus, combo_key
            )
        else:
            # Report模式：标准报告
            return self._generate_standard_report(
                entity, articles, analysis_results, selected_dimensions, focus, combo_key
            )
    
    def _generate_qa_response(self, entity: Any, analysis_results: Dict,
                             original_query: str, articles: List[Any]) -> str:
        """生成QA模式的简洁响应"""
        response_parts = []
        
        # 直接回答
        for dimension_key, result in analysis_results.items():
            if result.get('content') and '未找到' not in result['content']:
                response_parts.append(result['content'])
                break  # QA模式只需要最相关的一个回答
        
        # 添加简短的证据说明
        if articles:
            response_parts.append(f"\n基于{len(articles)}篇相关文献的分析。")
        
        return '\n'.join(response_parts)
    
    def _generate_comparison_report(self, entity: Any, articles: List[Any],
                                   analysis_results: Dict, selected_dimensions: Dict,
                                   focus: str, combo_key: str) -> str:
        """生成比较模式的报告（包含评分）"""
        # 先生成标准报告
        report = self._generate_standard_report(
            entity, articles, analysis_results, selected_dimensions, focus, combo_key
        )
        
        # 添加评分部分
        score_section = [
            "",
            "---",
            "",
            "## 靶点综合评分",
            "",
            "基于以上分析，对当前靶点进行综合评分（满分10分）：",
            "",
            "- **治疗潜力**: _/3分",
            "- **安全性**: _/2分",
            "- **研究成熟度**: _/2分",
            "- **临床转化可行性**: _/2分",
            "- **市场前景**: _/1分",
            "",
            "**总分**: _/10分",
            "",
            "*评分说明*: 基于文献分析和当前研究进展的综合评估。"
        ]
        
        return report + '\n'.join(score_section)
    
    def _generate_standard_report(self, entity: Any, articles: List[Any],
                                 analysis_results: Dict, selected_dimensions: Dict,
                                 focus: str, combo_key: str) -> str:
        """生成标准报告（原有逻辑）"""
        report_parts = [
            "# 文献分析综合报告",
            "",
            f"**分析焦点**: {focus}",
            f"**实体组合类型**: {self._get_combo_description(combo_key)}",
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
        
        # 添加分析维度说明
        report_parts.extend([
            "## 分析维度",
            "",
            "基于输入实体组合，本次分析聚焦以下维度：",
            ""
        ])
        
        for i, (dim_key, question) in enumerate(selected_dimensions.items(), 1):
            report_parts.append(f"{i}. **{dim_key}**: {question}")
        
        report_parts.extend(["", "---", ""])
        
        # 添加各维度分析结果
        report_parts.append("## 详细分析")
        
        for dimension_key, result in analysis_results.items():
            report_parts.extend([
                "",
                f"### {dimension_key}",
                "",
                result.get('content', '无相关内容'),
                ""
            ])
        
        # 添加参考文献
        if self.ref_manager.references:
            report_parts.extend([
                "---",
                "",
                "## 参考文献",
                ""
            ])
            for ref in self.ref_manager.get_reference_list():
                report_parts.append(
                    f"{ref['number']}. {ref['authors'][:50]}... {ref['title'][:100]}... "
                    f"*{ref['journal']}* ({ref['year']}). "
                    f"[PMID: {ref['pmid']}]({ref['url']})"
                )
        
        return '\n'.join(report_parts)
    
    # === 以下是保持不变的辅助方法（示例） ===
    
    def _get_combination_key(self, entity: Any) -> str:
        """生成实体组合的键"""
        parts = []
        if getattr(entity, 'target', None): parts.append('T')
        if getattr(entity, 'disease', None): parts.append('D')
        if getattr(entity, 'therapy', None): parts.append('R')
        if getattr(entity, 'drug', None): parts.append('M')
        return ''.join(parts)
    
    def _entity_summary(self, entity: Any) -> str:
        """生成实体摘要"""
        parts = []
        if getattr(entity, 'target', None):
            parts.append(f"靶点: {entity.target}")
        if getattr(entity, 'disease', None):
            parts.append(f"疾病: {entity.disease}")
        if getattr(entity, 'drug', None):
            parts.append(f"药物: {entity.drug}")
        if getattr(entity, 'therapy', None):
            parts.append(f"治疗方式: {entity.therapy}")
        return ', '.join(parts) if parts else "无特定实体"
    
    def _select_key_papers(self, articles: List[Any]) -> List[Dict]:
        """选择关键文献"""
        # 简单逻辑：返回前5篇
        key_papers = []
        for article in articles[:5]:
            key_papers.append({
                'pmid': getattr(article, 'pmid', ''),
                'title': getattr(article, 'title', ''),
                'authors': getattr(article, 'authors', ''),
                'journal': getattr(article, 'journal', ''),
                'year': getattr(article, 'year', ''),
                'relevance': 0.9  # 可以根据实际相关性计算
            })
        return key_papers
    
    def _assess_evidence_level(self, paper_count: int) -> str:
        """评估证据等级"""
        if paper_count >= 50:
            return "高（50+篇文献）"
        elif paper_count >= 20:
            return "中高（20-49篇文献）"
        elif paper_count >= 10:
            return "中（10-19篇文献）"
        elif paper_count >= 5:
            return "低中（5-9篇文献）"
        else:
            return "低（少于5篇文献）"
    
    def _get_combo_description(self, combo_key: str) -> str:
        """获取组合描述"""
        descriptions = {
            'T': '单一靶点',
            'D': '单一疾病',
            'R': '单一治疗方式',
            'M': '单一药物',
            'TD': '靶点-疾病',
            'TR': '靶点-治疗',
            'TM': '靶点-药物',
            'DR': '疾病-治疗',
            'DM': '疾病-药物',
            'RM': '治疗-药物',
            'TDR': '靶点-疾病-治疗',
            'TDM': '靶点-疾病-药物',
            'TRM': '靶点-治疗-药物',
            'DRM': '疾病-治疗-药物',
            'TDRM': '完整组合（靶点-疾病-治疗-药物）'
        }
        return descriptions.get(combo_key, '自定义组合')
    
    # 其他现有方法保持不变...
    def _build_query(self, entity: Any, search_terms: List[str]) -> str:
        """构建查询字符串"""
        parts = []
        
        if getattr(entity, 'disease', None) and getattr(entity, 'target', None):
            parts.append(f'("{entity.disease}" AND "{entity.target}")')
        elif getattr(entity, 'disease', None):
            parts.append(f'"{entity.disease}"')
        elif getattr(entity, 'target', None):
            parts.append(f'"{entity.target}"')
        
        if getattr(entity, 'therapy', None):
            parts.append(f'"{entity.therapy}"')
            
        if getattr(entity, 'drug', None):
            parts.append(f'"{entity.drug}"')
        
        if not parts and search_terms:
            parts = [f'"{term}"' for term in search_terms[:3]]
        
        return ' AND '.join(parts) if parts else ''
    
    def _empty_result(self, query: str, search_terms: List[str]) -> Dict[str, Any]:
        """返回空结果"""
        return self._create_no_results_response('report', '', query, search_terms)
    
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
    
    def _select_dimensions(self, entity: Any) -> Dict[str, str]:
        """选择分析维度（简化版）"""
        dimensions = {}
        
        if getattr(entity, 'target', None):
            dimensions['mechanism'] = f'{entity.target}的作用机制是什么？'
        
        if getattr(entity, 'disease', None):
            dimensions['pathology'] = f'{entity.disease}的病理机制是什么？'
        
        if getattr(entity, 'therapy', None):
            dimensions['treatment'] = f'{entity.therapy}的治疗策略是什么？'
        
        # 限制最多3个维度
        if len(dimensions) > 3:
            items = list(dimensions.items())[:3]
            dimensions = dict(items)
        
        return dimensions
    
    def _add_pmid_to_context(self, context, chunks):
        """在context中添加PMID标记"""
        if isinstance(context, str):
            parts = []
            for chunk in chunks:
                if hasattr(chunk, 'doc_id') and chunk.doc_id:
                    chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    parts.append(f"{chunk_text} [REF:{chunk.doc_id}]")
                else:
                    chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    parts.append(chunk_text)
            return "\n\n".join(parts) if parts else context
        return context
    
    def _format_citations(self, text):
        """将[REF:PMID]替换为[编号](URL)格式"""
        def replace_ref(match):
            pmid = match.group(1)
            ref_num = self.ref_manager.get_ref_number(pmid)
            if ref_num:
                return f"[{ref_num}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"
            return match.group(0)
        
        return re.sub(r'\[REF:(\d+)\]', replace_ref, text)