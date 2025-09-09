# agent_core/agents/specialists/patent_expert.py
"""
专利分析专家 - 支持Mock模式快速生成
保留完整的原始API分析流程
"""

import logging
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from agent_core.agents.tools.retrievers.patent_retriever import PatentRetriever
from agent_core.agents.tools.retrievers.patent_mock_generator import PatentMockGenerator
from agent_core.clients.llm_client import call_llm

logger = logging.getLogger(__name__)

@dataclass
class PatentAnalysisResult:
    """专利分析结果"""
    gene_target: str
    statistics: Dict[str, Any]  # 100篇专利的统计数据
    detailed_analyses: List[Dict[str, Any]]  # TOP 10专利的详细分析
    final_report: str  # 最终综合报告

class PatentAnalysisPrompts:
    """专利分析Prompt模板 - 完全保持原始代码"""
    
    def __init__(self, target_gene: str):
        self.target_gene = target_gene
    
    def description_analysis_prompt(self, description_text: str, patent_info: Dict) -> str:
        """说明书分析prompt - 与原始代码完全一致"""
        return f"""
作为专利技术专家，请深度分析以下{self.target_gene}基因相关专利的说明书，并以连贯的段落形式输出分析结果。

专利号：{patent_info['patent_number']}
申请人：{patent_info['assignee']}
申请日：{patent_info['application_date']}

说明书内容：
{description_text}

请按以下结构分析（每部分用2-3个完整段落表述）：

## 1. 技术概述（2段）
第一段：简要描述这是什么类型的技术（RNAi/抗体/小分子/基因编辑/细胞治疗等），针对{self.target_gene}靶点要解决什么具体问题。
第二段：说明核心创新点是什么，与现有技术相比的主要改进在哪里。

## 2. 技术方案分析（3段）
第一段：详细描述具体的技术方案。根据技术类型分析关键要素（序列设计、化合物结构、载体构建等）。
第二段：分析优化或改进策略（化学修饰、结构优化、递送系统等）。
第三段：与同领域其他专利技术的对比，突出本专利的独特性。

## 3. 实验验证（3段）
第一段：概述实验设计的整体思路，包括体外、体内实验的层次安排。
第二段：详细描述最关键的实验结果，包括具体数据（IC50、EC50、抑制率、持续时间等）。
第三段：安全性评估和临床转化考虑。如果有临床试验设计，说明主要终点和给药方案。

## 4. 商业价值评估（2段）
第一段：评估{self.target_gene}相关疾病的市场规模和竞争格局。该技术的目标适应症是什么？市场潜力如何？
第二段：分析专利技术的可实施性和商业化前景。生产工艺是否成熟？成本是否可控？临床开发路径是否清晰？

## 5. 关键技术参数提取
请特别提取以下关键信息（如果存在）：
- 核心序列/化合物：具体序列号或化学结构
- 靶向机制：{self.target_gene}的作用位点或机制
- 实验数据：关键的量化指标
- 技术特征：独特的技术特点
- 临床方案：剂量、给药途径、频率（如有）

输出要求：
- 使用完整流畅的段落，避免碎片化列表
- 数据自然融入叙述中
- 保持专业但易读的文风
- 总字数控制在1000-1500字
"""
    
    def claims_analysis_prompt(self, claims_text: str, patent_info: Dict) -> str:
        """权利要求分析prompt - 与原始代码完全一致"""
        return f"""
作为专利法律专家，请分析以下{self.target_gene}基因相关专利的权利要求书，并以适合专业报告的段落形式输出。

专利号：{patent_info['patent_number']}
申请人：{patent_info['assignee']}

权利要求书：
{claims_text}

请按以下结构分析（每部分用2-3个完整段落表述）：

## 1. 权利要求架构概述（2段）
第一段：描述权利要求的整体结构，包括权利要求数量、独立权利要求的类型分布。
第二段：分析权利要求之间的逻辑关系和保护策略。

## 2. 核心保护范围分析（3段）
第一段：深入分析独立权利要求的保护范围，特别是与{self.target_gene}相关的必要技术特征。
第二段：分析关键限定条件对保护范围的影响。
第三段：评估其他独立权利要求的补充作用。

## 3. 技术特征递进策略（2段）
第一段：分析从属权利要求的递进逻辑和层次结构。
第二段：评价关键从属权利要求的价值和商业意义。

## 4. 法律稳定性与侵权分析（2段）
第一段：评估权利要求的法律稳定性（清楚性、支持性、创造性）。
第二段：分析侵权判定的关键要素和潜在规避路径。

## 5. 与其他{self.target_gene}专利的关系（1段）
分析该专利权利要求与其他主要申请人{self.target_gene}专利的潜在冲突或互补关系。

输出要求：
- 使用连贯的专业段落
- 法律分析结合商业考虑
- 总字数控制在800-1200字
"""
    
    def final_report_prompt(self, statistics: Dict, detailed_analyses: List[Dict]) -> str:
        """最终综合报告prompt - 与原始代码完全一致"""
        return f"""
你是专业的专利分析师，请基于以下数据撰写一份详细的{self.target_gene}基因相关专利技术综述报告。

【100篇专利统计数据】
{json.dumps(statistics, ensure_ascii=False, indent=2)}

【10篇核心专利详细分析】
{json.dumps(detailed_analyses, ensure_ascii=False, indent=2)}

请生成一份专业的专利技术综述报告，格式如下：

# {self.target_gene}基因相关全球专利竞争格局分析

## 一、专利数量、类型与地域分布

### 全球专利公开数量与类型（400字）
基于分析的100篇{self.target_gene}相关专利，详细说明：
- 专利总数和时间分布趋势
- 技术类型分布（各类技术占比）
- 主要申请人分布
- 法律状态统计

### 地域分布（300字）
分析专利的地域布局特点。

## 二、核心专利权利人及布局策略

基于10篇核心专利的深度分析，详细描述各主要玩家的技术策略。
[根据实际申请人情况动态生成各公司分析]

## 三、技术发展趋势与关键创新

### 技术路线对比（500字）
详细对比不同公司针对{self.target_gene}的技术方案差异。

### 关键技术参数汇总
整理所有核心专利的关键参数。

## 四、专利保护范围与法律风险

### 权利要求保护范围对比（400字）
对比不同专利的保护策略。

### 潜在冲突分析（300字）
识别可能的专利冲突点。

## 五、商业机会与投资建议

### 技术空白与机会（300字）
基于专利分析识别的{self.target_gene}领域机会。

### 投资与研发建议（300字）
- 最有前景的技术路线
- 需要规避的专利壁垒
- 潜在的合作机会

## 六、结论与展望

总结{self.target_gene}专利领域的发展现状和未来趋势（300字）。

【输出要求】
1. 必须基于提供的数据，不要编造信息
2. 包含具体的专利号、申请人、技术细节
3. 数据和分析要相互印证
4. 保持客观专业的语气
5. 总字数3000-4000字
"""

class PatentExpert:
    """专利分析专家 - 保持原始代码逻辑"""
    
    def __init__(self, use_mock: bool = True):
        """
        初始化专利专家
        
        Args:
            use_mock: 是否使用模拟数据
        """
        self.retriever = PatentRetriever(use_mock=use_mock)
        self.mock_generator = PatentMockGenerator() if use_mock else None
        self.use_mock = use_mock
        self.target_gene = None
        self.prompts = None
        self.initial_patents = 100  # 初始检索数量
        self.top_patents = 10  # TOP专利数量
        
        logger.info(f"PatentExpert initialized (mock_mode={use_mock})")
    
    async def analyze(self, gene_target: str, config: Dict = None) -> PatentAnalysisResult:
        """
        执行专利分析
        
        Args:
            gene_target: 基因靶点
            config: 分析配置
            
        Returns:
            专利分析结果
        """
        self.target_gene = gene_target
        self.prompts = PatentAnalysisPrompts(gene_target)
        
        if self.use_mock:
            # Mock模式：直接生成数据
            return await self._analyze_with_mock(gene_target, config)
        else:
            # 真实模式：使用原始流程
            return await self._analyze_with_api(gene_target, config)
    
    async def _analyze_with_mock(self, gene_target: str, config: Dict = None) -> PatentAnalysisResult:
        """使用模拟数据进行分析"""
        logger.info(f"🚀 Starting MOCK analysis for {gene_target}")
        
        # Step 1: 生成统计数据
        logger.info("Step 1: Generating mock statistics...")
        statistics = self.mock_generator.generate_mock_statistics(gene_target)
        logger.info(f"✅ Generated statistics for {statistics['total_patents']} patents")
        
        # Step 2: 生成详细分析
        logger.info("Step 2: Generating mock detailed analyses...")
        detailed_analyses = self.mock_generator.generate_mock_detailed_analyses(gene_target, count=10)
        logger.info(f"✅ Generated {len(detailed_analyses)} detailed analyses")
        
        # Step 3: 生成最终报告
        logger.info("Step 3: Generating final report...")
        final_prompt = self.prompts.final_report_prompt(statistics, detailed_analyses)
        final_report = call_llm(final_prompt)
        
        logger.info(f"✅ {gene_target} patent analysis completed!")
        
        return PatentAnalysisResult(
            gene_target=gene_target,
            statistics=statistics,
            detailed_analyses=detailed_analyses,
            final_report=final_report
        )
    
    async def _analyze_with_api(self, gene_target: str, config: Dict = None) -> PatentAnalysisResult:
        """使用真实API进行分析 - 保持原始代码逻辑"""
        
        # 配置参数
        config = config or {}
        self.initial_patents = config.get("initial_patents", 100)
        self.top_patents = config.get("top_patents", 10)
        
        logger.info("=" * 50)
        logger.info(f"🚀 Step 1: 获取{gene_target}相关专利数据")
        
        # ========== Step 1: 获取专利数据 ==========
        # 1.1 搜索专利
        search_results = self.retriever.search_patents(gene_target, limit=self.initial_patents)
        if not search_results:
            logger.error(f"未找到{gene_target}相关专利")
            return PatentAnalysisResult(gene_target, {}, [], "")
        
        # 1.2 处理基础数据（转换为DataFrame以匹配原始代码）
        df_patents = self._process_initial_patents(search_results)
        logger.info(f"✅ 处理了 {len(df_patents)} 篇专利")
        
        # ========== Step 2: 获取摘要和统计分析 ==========
        logger.info("=" * 50)
        logger.info("🔍 Step 2: 获取摘要并进行统计分析")
        
        # 2.1 补充摘要和法律状态
        df_patents = self._enrich_with_abstracts(df_patents)
        
        # 2.2 统计分析
        statistics = self._analyze_patent_statistics(df_patents)
        statistics["target_gene"] = gene_target
        logger.info("📊 专利统计分析完成")
        
        # 显示统计结果
        self._display_statistics(statistics)
        
        # 2.3 评分和排序
        df_patents = self._score_and_rank_patents(df_patents)
        
        # ========== Step 3: 选择Top 10专利 ==========
        logger.info("=" * 50)
        logger.info(f"🎯 Step 3: 选择Top {self.top_patents}专利进行深度分析")
        
        top10_patents = df_patents.head(self.top_patents)
        self._display_top_patents(top10_patents)
        
        # ========== Step 4: 深度分析Top 10专利 ==========
        logger.info("=" * 50)
        logger.info("🔬 Step 4: 深度分析核心专利")
        
        detailed_analyses = []
        
        for idx, (_, patent) in enumerate(top10_patents.iterrows(), 1):
            logger.info(f"分析专利 {idx}/{self.top_patents}: {patent['patent_number']}")
            
            # 4.1 获取说明书
            description = self.retriever.get_description(
                patent["patent_id"], 
                patent["patent_number"]
            )
            
            # 4.2 获取权利要求
            claims = self.retriever.get_claims(
                patent["patent_id"],
                patent["patent_number"]
            )
            
            if description and claims:
                # 4.3 LLM分析说明书
                desc_prompt = self.prompts.description_analysis_prompt(
                    description, 
                    patent.to_dict()
                )
                desc_analysis =call_llm(desc_prompt)
                
                # 4.4 LLM分析权利要求
                claims_prompt = self.prompts.claims_analysis_prompt(
                    claims,
                    patent.to_dict()
                )
                claims_analysis = call_llm(claims_prompt)
                
                detailed_analyses.append({
                    "patent_number": patent["patent_number"],
                    "assignee": patent["assignee"],
                    "application_date": patent["application_date"],
                    "title": patent["title"],
                    "technical_analysis": desc_analysis,
                    "legal_analysis": claims_analysis
                })
                
                logger.info(f"✅ 完成分析: {patent['patent_number']}")
            else:
                logger.warning(f"⚠️ 无法获取完整内容: {patent['patent_number']}")
            
            time.sleep(2)  # API限流
        
        # ========== Step 5: 生成综合报告 ==========
        logger.info("=" * 50)
        logger.info("📝 Step 5: 生成综合报告")
        
        # 5.1 准备数据
        statistics["top_patents"] = top10_patents[
            ["patent_number", "assignee", "final_score"]
        ].to_dict("records")
        
        # 5.2 生成最终报告
        final_prompt = self.prompts.final_report_prompt(statistics, detailed_analyses)
        final_report = call_llm(final_prompt)
        
        logger.info(f"✅ {gene_target}专利分析完成！")
        
        # 构建返回结果
        return PatentAnalysisResult(
            gene_target=gene_target,
            statistics=statistics,
            detailed_analyses=detailed_analyses,
            final_report=final_report
        )
    
    def _process_initial_patents(self, patents: List[Dict]) -> pd.DataFrame:
        """处理初始专利数据 - 匹配原始代码的DataFrame结构"""
        processed = []
        
        for i, patent in enumerate(patents, 1):
            if i % 20 == 0:
                logger.info(f"处理进度: {i}/{len(patents)}")
            
            # 提取基础信息
            patent_info = {
                "patent_id": patent.get("patent_id"),
                "patent_number": patent.get("pn"),
                "title": self._extract_title(patent),
                "assignee": patent.get("current_assignee", ""),
                "application_date": str(patent.get("apdt", "")),
                "publication_date": str(patent.get("pbdt", "")),
                "abstract": "",
                "legal_status": "",
                "score": patent.get("score", 0)
            }
            
            processed.append(patent_info)
            time.sleep(0.1)  # API限流
        
        return pd.DataFrame(processed)
    
    def _extract_title(self, patent: Dict) -> str:
        """提取标题"""
        title = patent.get("title", "")
        if isinstance(title, dict):
            title = title.get("en") or title.get("zh", "")
        return str(title)
    
    def _enrich_with_abstracts(self, df: pd.DataFrame) -> pd.DataFrame:
        """补充摘要和法律状态"""
        logger.info("📄 获取摘要和法律状态...")
        
        for idx, row in df.iterrows():
            if idx % 10 == 0:
                logger.info(f"进度: {idx}/{len(df)}")
            
            # 获取摘要
            biblio = self.retriever.get_simple_bibliography(row["patent_id"], row["patent_number"])
            if biblio:
                abstracts = biblio.get("bibliographic_data", {}).get("abstracts", [])
                if abstracts:
                    df.at[idx, "abstract"] = abstracts[0].get("text", "")[:500]
            
            # 获取法律状态
            legal = self.retriever.get_legal_status(row["patent_id"], row["patent_number"])
            if legal and isinstance(legal, list) and legal:
                legal_info = legal[0].get("patent_legal", {})
                status = legal_info.get("simple_legal_status", [])
                df.at[idx, "legal_status"] = ", ".join(status) if status else "Unknown"
            
            time.sleep(0.2)
        
        return df
    
    def _analyze_patent_statistics(self, df: pd.DataFrame) -> Dict:
        """统计分析专利 - 与原始代码保持一致"""
        stats = {
            "total_patents": len(df),
            "assignee_distribution": df["assignee"].value_counts().to_dict(),
            "year_distribution": df["application_date"].str[:4].value_counts().to_dict(),
            "legal_status_distribution": df["legal_status"].value_counts().to_dict()
        }
        
        # 基于基因名的动态技术类型识别
        tech_types = {
            "RNAi/siRNA": 0,
            "Antibody/mAb": 0,
            "Small Molecule": 0,
            "CRISPR/Gene Editing": 0,
            "Cell Therapy": 0,
            "Protein/Peptide": 0,
            "Gene Therapy": 0,
            "Other": 0
        }
        
        for _, row in df.iterrows():
            text = (str(row["title"]) + " " + str(row["abstract"])).lower()
            
            # 检测技术类型
            if any(kw in text for kw in ["rnai", "sirna", "interference", "oligonucleotide", "antisense"]):
                tech_types["RNAi/siRNA"] += 1
            elif any(kw in text for kw in ["antibody", "mab", "immunoglobulin", "monoclonal"]):
                tech_types["Antibody/mAb"] += 1
            elif any(kw in text for kw in ["compound", "inhibitor", "small molecule", "chemical"]):
                tech_types["Small Molecule"] += 1
            elif any(kw in text for kw in ["crispr", "cas9", "gene editing", "genome editing"]):
                tech_types["CRISPR/Gene Editing"] += 1
            elif any(kw in text for kw in ["car-t", "cell therapy", "tcr", "nk cell"]):
                tech_types["Cell Therapy"] += 1
            elif any(kw in text for kw in ["protein", "peptide", "fusion protein", "recombinant"]):
                tech_types["Protein/Peptide"] += 1
            elif any(kw in text for kw in ["gene therapy", "aav", "viral vector", "lentivirus"]):
                tech_types["Gene Therapy"] += 1
            else:
                tech_types["Other"] += 1
        
        stats["technology_distribution"] = tech_types
        
        return stats
    
    def _score_and_rank_patents(self, df: pd.DataFrame) -> pd.DataFrame:
        """评分并排序专利 - 与原始代码保持一致"""
        logger.info("⚖️ 专利评分中...")
        
        # 构建与目标基因相关的关键词列表
        gene_lower = self.target_gene.lower()
        gene_keywords = [
            gene_lower,
            self.target_gene.upper(),
            "therapeutic", "treatment", "inhibitor", "agonist", "antagonist",
            "disease", "disorder", "cancer", "tumor", "diabetes", "obesity",
            "inflammation", "metabolic", "cardiovascular", "neurological"
        ]
        
        # 顶级制药公司列表
        top_pharma_companies = [
            "ROCHE", "NOVARTIS", "PFIZER", "MERCK", "JOHNSON", "SANOFI", 
            "GLAXOSMITHKLINE", "GSK", "ASTRAZENECA", "ABBVIE", "BRISTOL",
            "LILLY", "AMGEN", "GILEAD", "REGENERON", "VERTEX", "BIOGEN",
            "ARROWHEAD", "ALNYLAM", "MODERNA", "BIONTECH", "WAVE"
        ]
        
        for idx, row in df.iterrows():
            score = 0
            
            # 1. 摘要和标题相关度（0-35分）
            text = (str(row["title"]) + " " + str(row["abstract"])).lower()
            
            # 基因名称出现得分
            gene_count = text.count(gene_lower)
            score += min(gene_count * 5, 20)
            
            # 其他关键词得分
            keyword_score = sum(2 for kw in gene_keywords[2:] if kw in text)
            score += min(keyword_score, 15)
            
            # 2. 申请人权重（0-20分）
            assignee = str(row["assignee"]).upper()
            if any(comp in assignee for comp in top_pharma_companies):
                score += 20
            elif assignee and "UNIVERSITY" in assignee:
                score += 10
            elif assignee:
                score += 5
            
            # 3. 时间新鲜度（0-15分）
            pub_date = str(row["publication_date"])
            if pub_date >= "20240000":
                score += 15
            elif pub_date >= "20230000":
                score += 12
            elif pub_date >= "20220000":
                score += 8
            elif pub_date >= "20200000":
                score += 5
            
            # 4. 法律状态（0-10分）
            legal = str(row["legal_status"]).lower()
            if "grant" in legal or "授权" in legal:
                score += 10
            elif "pending" in legal or "审查" in legal:
                score += 5
            
            # 5. 原始相关度分数（0-20分）
            original_score = row["score"]
            if original_score > 80:
                score += 20
            elif original_score > 60:
                score += 15
            elif original_score > 40:
                score += 10
            elif original_score > 20:
                score += 5
            
            df.at[idx, "final_score"] = score
        
        # 排序
        df_sorted = df.sort_values("final_score", ascending=False)
        
        return df_sorted
    
    def _display_statistics(self, statistics: Dict):
        """显示统计结果"""
        print(f"\n{self.target_gene}相关技术类型分布:")
        for tech, count in statistics["technology_distribution"].items():
            print(f"  {tech}: {count}件")
        
        print(f"\n{self.target_gene}专利主要申请人（前5）:")
        assignee_dist = dict(list(statistics["assignee_distribution"].items())[:5])
        for assignee, count in assignee_dist.items():
            print(f"  {assignee}: {count}件")
    
    def _display_top_patents(self, top_patents: pd.DataFrame):
        """显示TOP专利"""
        print(f"\n{self.target_gene}相关Top {len(top_patents)}专利:")
        for idx, (_, row) in enumerate(top_patents.iterrows(), 1):
            print(f"{idx}. {row['patent_number']} - {row['assignee'][:30]} (Score: {row['final_score']})")