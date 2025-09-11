# agent_core/agents/specialists/literature_expert.py

"""
Literature Expert - 文献分析专家主控制模块
负责：整体流程控制、维度选择、报告生成
"""

from typing import Dict, List, Any, Optional
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
    
    def _get_combination_key(self, entity: Any) -> str:
        """生成实体组合的键"""
        parts = []
        if entity.target: parts.append('T')
        if entity.disease: parts.append('D')
        if entity.therapy: parts.append('R')  # R for theRapy
        if entity.drug: parts.append('M')  # M for Medicine
        return ''.join(parts)
    
    def _select_dimensions(self, entity: Any) -> Dict[str, str]:
        """根据实体组合动态选择分析维度"""
        
        combo_key = self._get_combination_key(entity)
        
        # 为16种组合定义维度配置
        dimension_configs = {
            # ========== 单一实体（4种）==========
            'T': {
                'target_function': f'{entity.target}的分子功能和生物学作用是什么？',
                'target_disease_association': f'{entity.target}与哪些疾病相关？',
                'target_druggability': f'{entity.target}的成药性和开发潜力如何？'
            },
            
            'D': {
                'disease_mechanism': f'{entity.disease}的发病机制是什么？',
                'disease_targets': f'{entity.disease}有哪些潜在治疗靶点？',
                'disease_treatment': f'{entity.disease}的治疗策略和进展如何？'
            },
            
            'R': {
                'therapy_mechanism': f'{entity.therapy}的作用原理是什么？',
                'therapy_applications': f'{entity.therapy}在哪些疾病中有应用价值？',
                'therapy_development': f'{entity.therapy}的技术发展和优化方向是什么？'
            },
            
            'M': {
                'drug_mechanism': f'{entity.drug}的作用机制和靶点是什么？',
                'drug_clinical': f'{entity.drug}的临床应用和疗效如何？',
                'drug_optimization': f'{entity.drug}的优化策略和发展方向是什么？'
            },
            
            # ========== 双实体组合（6种）==========
            'TD': {
                'td_mechanism': f'{entity.target}在{entity.disease}发病中的作用机制是什么？',
                'td_therapy': f'如何靶向{entity.target}治疗{entity.disease}？'
            },
            
            'TR': {
                'tr_feasibility': f'用{entity.therapy}方法靶向{entity.target}的可行性如何？',
                'tr_strategy': f'{entity.therapy}靶向{entity.target}的具体策略是什么？'
            },
            
            'TM': {
                'tm_interaction': f'{entity.drug}如何作用于{entity.target}靶点？',
                'tm_efficacy': f'{entity.drug}通过{entity.target}产生的治疗效果如何？'
            },
            
            'DR': {
                'dr_application': f'{entity.therapy}在{entity.disease}治疗中的应用价值如何？',
                'dr_evidence': f'{entity.therapy}治疗{entity.disease}的临床证据是什么？'
            },
            
            'DM': {
                'dm_efficacy': f'{entity.drug}治疗{entity.disease}的疗效如何？',
                'dm_mechanism': f'{entity.drug}改善{entity.disease}的作用机制是什么？'
            },
            
            'RM': {
                'rm_characteristics': f'{entity.drug}作为{entity.therapy}类药物的特点是什么？',
                'rm_comparison': f'{entity.drug}与其他{entity.therapy}类药物相比如何？'
            },
            
            # ========== 三实体组合（4种）==========
            'TDR': {
                'tdr_integrated': f'用{entity.therapy}靶向{entity.target}治疗{entity.disease}的综合策略是什么？',
                'tdr_evidence': f'{entity.therapy}通过{entity.target}治疗{entity.disease}的证据如何？'
            },
            
            'TDM': {
                'tdm_mechanism': f'{entity.drug}通过{entity.target}治疗{entity.disease}的完整机制是什么？',
                'tdm_precision': f'{entity.drug}在{entity.target}阳性{entity.disease}患者中的精准应用如何？'
            },
            
            'TRM': {
                'trm_innovation': f'{entity.drug}作为{entity.therapy}靶向{entity.target}的创新点是什么？',
                'trm_optimization': f'如何优化{entity.drug}这种{entity.therapy}对{entity.target}的作用？'
            },
            
            'DRM': {
                'drm_positioning': f'{entity.drug}作为{entity.therapy}在{entity.disease}治疗中的定位如何？',
                'drm_value': f'{entity.drug}体现{entity.therapy}治疗{entity.disease}的价值是什么？'
            },
            
            # ========== 四实体组合（1种）==========
            'TDRM': {
                'comprehensive': f'{entity.drug}作为{entity.therapy}通过{entity.target}治疗{entity.disease}的完整分析',
                'optimization': f'如何优化这个完整的治疗方案？'
            },
            
            # ========== 空查询（1种）==========
            '': {
                'general': '请分析提供的文献内容'
            }
        }
        
        # 获取对应的维度配置
        if combo_key in dimension_configs:
            selected = dimension_configs[combo_key]
        else:
            # 如果没有匹配，使用默认维度
            selected = self._get_default_dimensions(entity)
        
        # 限制维度数量（最多3个）
        if len(selected) > 3:
            # 只取前3个
            items = list(selected.items())[:3]
            selected = dict(items)
        
        print(f"[Literature Expert] Entity combination: {combo_key}")
        print(f"[Literature Expert] Selected dimensions:")
        for key, question in selected.items():
            print(f"  - {key}: {question}")
        
        return selected
    
    def _get_default_dimensions(self, entity: Any) -> Dict[str, str]:
        """获取默认维度（兜底方案）"""
        dimensions = {}
        
        # 根据存在的实体生成通用问题
        if entity.target:
            dimensions['target_general'] = f'{entity.target}的功能和治疗潜力是什么？'
        if entity.disease:
            dimensions['disease_general'] = f'{entity.disease}的机制和治疗策略是什么？'
        if entity.therapy:
            dimensions['therapy_general'] = f'{entity.therapy}的应用和发展是什么？'
        if entity.drug:
            dimensions['drug_general'] = f'{entity.drug}的作用和临床价值是什么？'
        
        # 如果有多个实体，添加关系问题
        entity_count = sum([bool(entity.target), bool(entity.disease), 
                           bool(entity.therapy), bool(entity.drug)])
        if entity_count >= 2:
            dimensions['relationship'] = '这些要素之间的关系和协同作用是什么？'
        
        return dimensions
    
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
        
        # 2. 构建RAG索引并处理引用
        self.rag.process_articles(articles)
        self._process_articles_references(articles)
        print(f"[Literature Expert] RAG processing complete")
        
        # 3. 动态选择分析维度（基于实体组合）
        selected_dimensions = self._select_dimensions(entity)
        
        # 4. 执行选定维度的分析
        analysis_results = {}
        combo_key = self._get_combination_key(entity)
        
        for dimension_key, dimension_question in selected_dimensions.items():
            print(f"[Literature Expert] Analyzing {dimension_key}")
            analysis_results[dimension_key] = await self._analyze_dimension(
                entity=entity,
                dimension_key=dimension_key,
                dimension_question=dimension_question,
                combo_key=combo_key
            )
        
        # 5. 生成综合报告
        report = await self._generate_comprehensive_report(
            entity=entity,
            articles=articles,
            analysis_results=analysis_results,
            selected_dimensions=selected_dimensions,
            focus=focus,
            combo_key=combo_key
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
            search_terms=search_terms,
            references=self.ref_manager.get_reference_list()
        )
        
        print(f"[Literature Expert] Analysis complete")
        
        return self._result_to_dict(result)
    
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
    
    async def _analyze_dimension(self, entity: Any, dimension_key: str, 
                                dimension_question: str, combo_key: str) -> Dict:
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
        
        # 3. 使用组合prompt（调用16个模板中的对应模板）
        prompt = self.prompts.get_combination_prompt(entity, formatted_context)
        
        # 4. 调用LLM进行分析
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_message="你是一个专业的生物医学研究助手。请使用段落式写作，每段200-300字，不要使用列表。"
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
                                            focus: str,
                                            combo_key: str) -> str:
        """生成综合报告"""
        
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
    
    def _get_combo_description(self, combo_key: str) -> str:
        """获取组合类型的描述"""
        descriptions = {
            'T': '单一靶点分析',
            'D': '单一疾病分析',
            'R': '单一治疗方式分析',
            'M': '单一药物分析',
            'TD': '靶点-疾病关联分析',
            'TR': '靶点-治疗方式分析',
            'TM': '靶点-药物分析',
            'DR': '疾病-治疗方式分析',
            'DM': '疾病-药物分析',
            'RM': '治疗方式-药物分析',
            'TDR': '靶点-疾病-治疗综合分析',
            'TDM': '靶点-疾病-药物综合分析',
            'TRM': '靶点-治疗-药物综合分析',
            'DRM': '疾病-治疗-药物综合分析',
            'TDRM': '全要素综合分析',
            '': '通用分析'
        }
        return descriptions.get(combo_key, '组合分析')
    
    def _get_dimension_display_name(self, dimension_key: str) -> str:
        """获取维度的显示名称"""
        # 根据维度键的前缀来生成显示名称
        if dimension_key.startswith('target_'):
            return '靶点' + dimension_key.replace('target_', '').replace('_', ' ').title()
        elif dimension_key.startswith('disease_'):
            return '疾病' + dimension_key.replace('disease_', '').replace('_', ' ').title()
        elif dimension_key.startswith('therapy_'):
            return '治疗' + dimension_key.replace('therapy_', '').replace('_', ' ').title()
        elif dimension_key.startswith('drug_'):
            return '药物' + dimension_key.replace('drug_', '').replace('_', ' ').title()
        elif dimension_key.startswith('td_'):
            return '靶点-疾病' + dimension_key.replace('td_', '').replace('_', ' ').title()
        elif dimension_key.startswith('tr_'):
            return '靶点-治疗' + dimension_key.replace('tr_', '').replace('_', ' ').title()
        elif dimension_key.startswith('tm_'):
            return '靶点-药物' + dimension_key.replace('tm_', '').replace('_', ' ').title()
        elif dimension_key.startswith('dr_'):
            return '疾病-治疗' + dimension_key.replace('dr_', '').replace('_', ' ').title()
        elif dimension_key.startswith('dm_'):
            return '疾病-药物' + dimension_key.replace('dm_', '').replace('_', ' ').title()
        elif dimension_key.startswith('rm_'):
            return '治疗-药物' + dimension_key.replace('rm_', '').replace('_', ' ').title()
        elif dimension_key.startswith('tdr_'):
            return '综合策略分析'
        elif dimension_key.startswith('tdm_'):
            return '精准医疗分析'
        elif dimension_key.startswith('trm_'):
            return '创新治疗分析'
        elif dimension_key.startswith('drm_'):
            return '临床应用分析'
        else:
            return dimension_key.replace('_', ' ').title()
    
    def _select_key_papers(self, articles: List[Any]) -> List[Dict]:
        """选择关键文献"""
        sorted_articles = sorted(articles, key=lambda x: getattr(x, 'year', 0), reverse=True)
        
        key_papers = []
        for article in sorted_articles[:5]:
            key_papers.append({
                'pmid': getattr(article, 'pmid', ''),
                'title': getattr(article, 'title', '')[:150] + ('...' if len(getattr(article, 'title', '')) > 150 else ''),
                'authors': getattr(article, 'authors', [])[:3],
                'journal': getattr(article, 'journal', ''),
                'year': getattr(article, 'year', ''),
                'doi': getattr(article, 'doi', ''),
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{getattr(article, 'pmid', '')}/"
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
            search_terms=search_terms,
            references=[]
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
            'search_terms': result.search_terms,
            'references': result.references
        }