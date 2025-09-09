# agent_core/agents/specialists/literature_expert.py

"""
Literature Expert - 文献分析专家主控制模块
负责：整体流程控制、维度选择、报告生成
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

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


class LiteratureExpert:
    """文献分析专家 - 主控制类"""
    
    def __init__(self):
        # 初始化各个模块
        self.retriever = PubMedRetriever()
        self.rag = LiteratureRAG()
        self.prompts = LiteraturePrompts()
        self.llm = LLMClient()
        
        # 定义所有可能的分析维度模板
        self.dimension_templates = {
            # 单一基因/靶点维度
            'gene_disease_association': {
                'question': '该基因与哪些疾病相关？在不同疾病中的作用是什么？',
                'applicable': lambda e: e.target and not e.disease
            },
            'gene_mechanism': {
                'question': '该基因在疾病中的分子机制是什么？信号通路如何？',
                'applicable': lambda e: e.target and not e.disease
            },
            'gene_druggability': {
                'question': '该基因的成药性如何？有哪些药物开发策略？',
                'applicable': lambda e: e.target and not e.disease
            },
            
            # 单一疾病维度
            'disease_pathogenesis': {
                'question': '该疾病的发病机制是什么？主要病理特征有哪些？',
                'applicable': lambda e: e.disease and not e.target
            },
            'disease_treatment_landscape': {
                'question': '该疾病有哪些治疗方法？临床指南推荐什么？',
                'applicable': lambda e: e.disease and not e.target
            },
            'disease_targets': {
                'question': '该疾病有哪些潜在治疗基因靶点？机制如何？哪些正在开发中？',
                'applicable': lambda e: e.disease and not e.target
            },
            
            # 基因+疾病组合维度
            'gene_disease_mechanism': {
                'question': '该基因在该疾病发病机制中扮演什么角色？',
                'applicable': lambda e: e.target and e.disease
            },
            'gene_disease_therapy': {
                'question': '针对该基因治疗该疾病的策略有哪些？临床证据如何？',
                'applicable': lambda e: e.target and e.disease
            },
            'gene_disease_biomarker': {
                'question': '该基因作为该疾病的治疗靶点价值如何？',
                'applicable': lambda e: e.target and e.disease
            },
            
            # 治疗方式维度
            'therapy_mechanism': {
                'question': '该治疗方式的作用机制是什么？',
                'applicable': lambda e: e.therapy
            },
            'therapy_efficacy': {
                'question': '该治疗方式的临床疗效和安全性如何？',
                'applicable': lambda e: e.therapy
            },
            'therapy_applications': {
                'question': '该治疗方式适用于哪些疾病？研究广泛的靶点有哪些？发展前景如何？',
                'applicable': lambda e: e.therapy and not e.disease
            },
            
            # 药物维度
            'drug_mechanism': {
                'question': '该药物的作用机制和靶点是什么？',
                'applicable': lambda e: e.drug
            },
            'drug_clinical': {
                'question': '该药物的临床研究进展如何？',
                'applicable': lambda e: e.drug
            },
            'drug_market': {
                'question': '该药物的适应症和市场表现如何？',
                'applicable': lambda e: e.drug
            }
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
        
        # 1. 检索文献（使用retriever）
        query = self._build_query(entity, search_terms)
        articles = await self.retriever.search_by_entity(entity, search_terms, query)
        
        if not articles:
            print("[Literature Expert] No articles found")
            return self._empty_result(query, search_terms)
        
        print(f"[Literature Expert] Retrieved {len(articles)} articles")
        
        # 2. 构建RAG索引（使用RAG模块）
        self.rag.process_articles(articles)
        print(f"[Literature Expert] RAG processing complete")
        
        # 3. 动态选择分析维度
        selected_dimensions = self._select_dimensions(entity)
        
        # 4. 执行选定维度的分析
        analysis_results = {}
        for dimension_key, dimension_question in selected_dimensions.items():
            print(f"[Literature Expert] Analyzing {dimension_key}")
            analysis_results[dimension_key] = await self._analyze_dimension(
                entity=entity,
                dimension_key=dimension_key,
                dimension_question=dimension_question
            )
        
        # 5. 生成综合报告
        report = await self._generate_comprehensive_report(
            entity=entity,
            articles=articles,
            analysis_results=analysis_results,
            selected_dimensions=selected_dimensions,
            focus=focus
        )
        
        # 6. 构建返回结果
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
    
    def _select_dimensions(self, entity: Any) -> Dict[str, str]:
        """根据实体类型动态选择分析维度"""
        selected_dimensions = {}
        
        # 根据实体情况选择适用的维度
        for dim_key, dim_config in self.dimension_templates.items():
            if dim_config['applicable'](entity):
                selected_dimensions[dim_key] = dim_config['question']
        
        # 如果没有选中任何维度，使用通用维度
        if not selected_dimensions:
            selected_dimensions = self._get_default_dimensions(entity)
        
        # 限制维度数量（最多3个最相关的）
        selected_dimensions = self._prioritize_dimensions(selected_dimensions, entity)
        
        print(f"[Literature Expert] Selected dimensions for entity:")
        for key, question in selected_dimensions.items():
            print(f"  - {key}: {question}")
        
        return selected_dimensions
    
    def _prioritize_dimensions(self, dimensions: Dict[str, str], entity: Any, max_dims: int = 3) -> Dict[str, str]:
        """优先选择最重要的维度"""
        # 定义优先级规则
        priority_rules = []
        
        # 基因+疾病组合 - 最高优先级
        if entity.target and entity.disease:
            priority_rules = [
                'gene_disease_mechanism',    # 机制最重要
                'gene_disease_therapy',       # 治疗策略次之
                'gene_disease_biomarker'      # 生物标志物第三
            ]
        # 仅基因
        elif entity.target and not entity.disease:
            priority_rules = [
                'gene_disease_association',   # 疾病关联最重要
                'gene_mechanism',             # 分子机制
                'gene_druggability'           # 成药性
            ]
        # 仅疾病
        elif entity.disease and not entity.target:
            priority_rules = [
                'disease_pathogenesis',       # 发病机制
                'disease_targets',            # 治疗靶点
                'disease_treatment_landscape' # 治疗方法
            ]
        # 治疗方式相关
        elif entity.therapy:
            priority_rules = [
                'therapy_mechanism',      # 作用机制
                'therapy_efficacy',       # 疗效
                'therapy_applications'    # 应用范围
            ]
        # 药物相关
        elif entity.drug:
            priority_rules = [
                'drug_mechanism',         # 作用机制
                'drug_clinical',          # 临床进展
                'drug_market'            # 市场情况
            ]
        
        # 根据优先级规则选择维度
        prioritized = {}
        for rule in priority_rules:
            if rule in dimensions and len(prioritized) < max_dims:
                prioritized[rule] = dimensions[rule]
        
        # 补充其他维度
        for key, question in dimensions.items():
            if len(prioritized) >= max_dims:
                break
            if key not in prioritized:
                prioritized[key] = question
        
        return prioritized
    
    def _get_default_dimensions(self, entity: Any) -> Dict[str, str]:
        """获取默认维度"""
        return {
            'general_mechanism': '相关的分子机制和生物学过程是什么？',
            'clinical_relevance': '临床意义和应用价值如何？',
            'research_progress': '当前研究进展和未来方向是什么？'
        }
    
    async def _analyze_dimension(self, entity: Any, dimension_key: str, 
                                dimension_question: str) -> Dict:
        """分析单个维度"""
        
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
        
        # 2. 使用Prompts模块获取提示词
        prompt = self.prompts.get_dimension_prompt(
            entity=entity,
            dimension_key=dimension_key,
            dimension_question=dimension_question,
            context=formatted_context
        )
        
        # 3. 调用LLM进行分析
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_message="你是一个专业的生物医学研究助手，擅长分析文献并提供基于证据的见解。"
            )
            
            return {
                'content': response,
                'chunks_used': len(relevant_chunks),
                'pmids_referenced': list(set([c.doc_id for c in relevant_chunks])),
                'dimension_question': dimension_question
            }
            
        except Exception as e:
            print(f"[Literature Expert] Analysis failed for {dimension_key}: {e}")
            return {
                'content': f'{dimension_key}分析失败',
                'chunks_used': 0,
                'error': str(e),
                'dimension_question': dimension_question
            }
    
    def _build_query(self, entity: Any, search_terms: List[str]) -> str:
        """构建查询字符串"""
        parts = []
        
        if entity.disease and entity.target:
            parts.append(f'("{entity.disease}" AND "{entity.target}")')
        elif entity.disease:
            parts.append(f'"{entity.disease}"')
        elif entity.target:
            parts.append(f'"{entity.target}"')
        
        if entity.therapy:
            parts.append(f'"{entity.therapy}"')
            
        if entity.drug:
            parts.append(f'"{entity.drug}"')
        
        if not parts and search_terms:
            parts = [f'"{term}"' for term in search_terms[:3]]
        
        return ' AND '.join(parts) if parts else ''
    
    async def _generate_comprehensive_report(self, entity: Any, articles: List[Any],
                                            analysis_results: Dict,
                                            selected_dimensions: Dict,
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
        
        # 添加分析维度说明
        report_parts.extend([
            "## 分析维度",
            "",
            "基于输入实体类型，本次分析聚焦以下维度：",
            ""
        ])
        
        for i, (dim_key, question) in enumerate(selected_dimensions.items(), 1):
            report_parts.append(f"{i}. **{self._get_dimension_display_name(dim_key)}**: {question}")
        
        report_parts.extend(["", "---", ""])
        
        # 添加各维度分析结果
        for i, (dimension_key, result) in enumerate(analysis_results.items(), 1):
            if result.get('content'):
                display_name = self._get_dimension_display_name(dimension_key)
                question = result.get('dimension_question', '')
                
                report_parts.extend([
                    f"## {i}. {display_name}",
                    "",
                    f"*研究问题: {question}*",
                    "",
                    result['content'],
                    "",
                    f"*基于 {result.get('chunks_used', 0)} 个文献片段分析*",
                    "",
                    "---",
                    ""
                ])
        
        # 添加关键文献
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
        
        return "\n".join(report_parts)
    
    def _get_dimension_display_name(self, dimension_key: str) -> str:
        """获取维度的显示名称"""
        display_names = {
            'gene_disease_association': '基因-疾病关联分析',
            'gene_mechanism': '基因分子机制',
            'gene_druggability': '基因成药性评估',
            'disease_pathogenesis': '疾病发病机制',
            'disease_treatment_landscape': '疾病治疗现状',
            'disease_targets': '疾病治疗靶点',
            'gene_disease_mechanism': '基因在疾病中的作用机制',
            'gene_disease_therapy': '基因靶向治疗策略',
            'gene_disease_biomarker': '生物标志物价值',
            'therapy_mechanism': '治疗机制分析',
            'therapy_efficacy': '疗效与安全性',
            'therapy_applications': '治疗应用范围',
            'drug_mechanism': '药物作用机制',
            'drug_clinical': '药物临床进展',
            'drug_market': '药物市场分析',
            'general_mechanism': '一般机制分析',
            'clinical_relevance': '临床相关性',
            'research_progress': '研究进展'
        }
        
        return display_names.get(dimension_key, dimension_key.replace('_', ' ').title())
    
    def _select_key_papers(self, articles: List[Any]) -> List[Dict]:
        """选择关键文献"""
        sorted_articles = sorted(articles, key=lambda x: x.year, reverse=True)
        
        key_papers = []
        for article in sorted_articles[:5]:
            key_papers.append({
                'pmid': article.pmid,
                'title': article.title[:150] + ('...' if len(article.title) > 150 else ''),
                'authors': article.authors[:3],
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