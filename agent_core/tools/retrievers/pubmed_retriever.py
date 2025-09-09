# agent_core/tools/retrievers/pubmed_retriever.py

"""
PubMed Retriever - 文献检索模块
负责：PubMed搜索、文献获取、扩展搜索
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from Bio import Entrez
import xml.etree.ElementTree as ET
import hashlib

from agent_core.config.settings import config


# 配置Entrez
Entrez.email = config.pubmed_email
Entrez.api_key = config.pubmed_api_key


@dataclass
class PubMedArticle:
    """PubMed文章数据结构"""
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: str
    year: int
    doi: Optional[str] = None
    keywords: List[str] = None
    mesh_terms: List[str] = None
    publication_type: List[str] = None


class PubMedRetriever:
    """PubMed检索器"""
    
    def __init__(self):
        self.max_results = config.max_articles
        self.cache = {}  # 简单缓存
        
    async def search(self, query: str, max_results: int = None) -> List[PubMedArticle]:
        """
        执行基础搜索
        
        Args:
            query: 搜索查询字符串
            max_results: 最大结果数
            
        Returns:
            文献列表
        """
        if not query:
            return []
        
        # 检查缓存
        cache_key = hashlib.md5(f"{query}_{max_results}".encode()).hexdigest()
        if cache_key in self.cache:
            print(f"[PubMed] Using cached results for: {query}")
            return self.cache[cache_key]
            
        max_results = max_results or self.max_results
        
        try:
            # 搜索
            print(f"[PubMed] Searching: {query}")
            search_handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="relevance",
                usehistory="y"
            )
            search_results = Entrez.read(search_handle)
            search_handle.close()
            
            pmid_list = search_results["IdList"]
            
            if not pmid_list:
                print(f"[PubMed] No results found for: {query}")
                return []
            
            print(f"[PubMed] Found {len(pmid_list)} articles")
            
            # 获取详情
            articles = await self._fetch_articles(pmid_list)
            
            # 缓存结果
            self.cache[cache_key] = articles
            
            return articles
            
        except Exception as e:
            print(f"[PubMed] Search failed: {e}")
            return []
    
    async def search_by_entity(self, entity: Any, search_terms: List[str] = None, 
                              primary_query: str = None) -> List[PubMedArticle]:
        """
        基于实体的智能搜索
        
        Args:
            entity: 实体对象
            search_terms: 额外搜索词
            primary_query: 主查询
            
        Returns:
            文献列表
        """
        all_articles = []
        seen_pmids = set()
        
        # 1. 执行主查询
        if primary_query:
            articles = await self.search(primary_query, self.max_results)
            for article in articles:
                if article.pmid not in seen_pmids:
                    all_articles.append(article)
                    seen_pmids.add(article.pmid)
        
        # 2. 基于实体构建查询
        entity_queries = self._build_entity_queries(entity)
        
        for query in entity_queries:
            if len(all_articles) >= self.max_results:
                break
                
            articles = await self.search(query, 30)
            for article in articles:
                if article.pmid not in seen_pmids and len(all_articles) < self.max_results:
                    all_articles.append(article)
                    seen_pmids.add(article.pmid)
        
        # 3. 使用搜索词扩展
        if search_terms and len(all_articles) < 20:
            for term in search_terms[:3]:
                if len(all_articles) >= self.max_results:
                    break
                    
                articles = await self.search(term, 20)
                for article in articles:
                    if article.pmid not in seen_pmids and len(all_articles) < self.max_results:
                        all_articles.append(article)
                        seen_pmids.add(article.pmid)
        
        print(f"[PubMed] Total articles retrieved: {len(all_articles)}")
        return all_articles
    
    def _build_entity_queries(self, entity: Any) -> List[str]:
        """根据实体构建多个查询"""
        queries = []
        
        # 组合查询
        if entity.disease and entity.target:
            queries.append(f'("{entity.disease}"[Title/Abstract] AND "{entity.target}"[Title/Abstract])')
            queries.append(f'("{entity.disease}" AND "{entity.target}" AND mechanism)')
            queries.append(f'("{entity.disease}" AND "{entity.target}" AND treatment)')
        
        # 单独查询
        if entity.target:
            queries.append(f'"{entity.target}"[Title/Abstract]')
            queries.append(f'("{entity.target}" AND (disease OR disorder OR cancer))')
            
        if entity.disease:
            queries.append(f'"{entity.disease}"[Title/Abstract]')
            queries.append(f'("{entity.disease}" AND (treatment OR therapy))')
            
        if entity.therapy:
            queries.append(f'"{entity.therapy}"[Title/Abstract]')
            queries.append(f'("{entity.therapy}" AND clinical trial)')
            
        if entity.drug:
            queries.append(f'"{entity.drug}"[Title/Abstract]')
            queries.append(f'("{entity.drug}" AND (efficacy OR safety))')
        
        return queries
    
    async def _fetch_articles(self, pmid_list: List[str]) -> List[PubMedArticle]:
        """批量获取文章详情"""
        articles = []
        
        # 分批获取（每批最多200个）
        batch_size = 200
        for i in range(0, len(pmid_list), batch_size):
            batch = pmid_list[i:i + batch_size]
            
            try:
                fetch_handle = Entrez.efetch(
                    db="pubmed",
                    id=",".join(batch),
                    retmode="xml"
                )
                
                xml_data = fetch_handle.read()
                fetch_handle.close()
                
                batch_articles = self._parse_xml(xml_data)
                articles.extend(batch_articles)
                
                # 避免请求过快
                await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"[PubMed] Failed to fetch batch {i//batch_size + 1}: {e}")
                continue
        
        return articles
    
    def _parse_xml(self, xml_data: str) -> List[PubMedArticle]:
        """解析PubMed XML"""
        articles = []
        
        try:
            root = ET.fromstring(xml_data)
            
            for elem in root.findall(".//PubmedArticle"):
                try:
                    article = self._parse_single_article(elem)
                    if article:
                        articles.append(article)
                except Exception as e:
                    print(f"[PubMed] Failed to parse article: {e}")
                    continue
                    
        except Exception as e:
            print(f"[PubMed] XML parse failed: {e}")
        
        return articles
    
    def _parse_single_article(self, elem: ET.Element) -> Optional[PubMedArticle]:
        """解析单篇文章"""
        # 基础信息
        pmid = elem.findtext(".//PMID", "")
        if not pmid:
            return None
            
        title = elem.findtext(".//ArticleTitle", "")
        
        # 摘要处理
        abstract_parts = []
        for abstract_elem in elem.findall(".//AbstractText"):
            label = abstract_elem.get("Label", "")
            text = abstract_elem.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract = " ".join(abstract_parts)
        
        # 期刊信息
        journal = elem.findtext(".//Journal/Title", "")
        
        # 年份
        year = 0
        year_elem = elem.find(".//PubDate/Year")
        if year_elem is not None:
            try:
                year = int(year_elem.text)
            except:
                pass
        
        # 如果没有年份，尝试MedlineDate
        if year == 0:
            medline_date = elem.findtext(".//PubDate/MedlineDate", "")
            if medline_date:
                try:
                    year = int(medline_date[:4])
                except:
                    pass
        
        # 作者
        authors = []
        for author in elem.findall(".//Author")[:10]:  # 最多10个作者
            last = author.findtext("LastName", "")
            first = author.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {first}".strip())
        
        # DOI
        doi = None
        for id_elem in elem.findall(".//ArticleId"):
            if id_elem.get("IdType") == "doi":
                doi = id_elem.text
                break
        
        # 关键词
        keywords = []
        for keyword in elem.findall(".//Keyword"):
            kw = keyword.text
            if kw:
                keywords.append(kw)
        
        # MeSH术语
        mesh_terms = []
        for mesh in elem.findall(".//MeshHeading/DescriptorName"):
            term = mesh.text
            if term:
                mesh_terms.append(term)
        
        # 文章类型
        publication_type = []
        for pub_type in elem.findall(".//PublicationType"):
            ptype = pub_type.text
            if ptype:
                publication_type.append(ptype)
        
        return PubMedArticle(
            pmid=pmid,
            title=title,
            abstract=abstract,
            authors=authors,
            journal=journal,
            year=year,
            doi=doi,
            keywords=keywords,
            mesh_terms=mesh_terms,
            publication_type=publication_type
        )
    
    async def get_related_articles(self, pmid: str, max_results: int = 20) -> List[PubMedArticle]:
        """获取相关文章"""
        try:
            # 使用elink获取相关文章
            link_handle = Entrez.elink(
                dbfrom="pubmed",
                db="pubmed",
                id=pmid,
                linkname="pubmed_pubmed"
            )
            link_results = Entrez.read(link_handle)
            link_handle.close()
            
            # 提取相关文章ID
            related_ids = []
            for link_set in link_results[0]["LinkSetDb"]:
                if link_set["LinkName"] == "pubmed_pubmed":
                    for link in link_set["Link"][:max_results]:
                        related_ids.append(link["Id"])
                    break
            
            if related_ids:
                return await self._fetch_articles(related_ids)
            
        except Exception as e:
            print(f"[PubMed] Failed to get related articles: {e}")
        
        return []
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        print("[PubMed] Cache cleared")