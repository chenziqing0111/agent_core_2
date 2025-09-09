# agent_core/tools/retrievers/pubmed_retriever.py

"""
PubMed Retriever
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from Bio import Entrez
import xml.etree.ElementTree as ET

from agent_core.config.settings import config


# 配置Entrez
Entrez.email = config.pubmed_email
Entrez.api_key = config.pubmed_api_key


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    abstract: str
    authors: List[str]
    journal: str
    year: int
    doi: Optional[str] = None


class PubMedRetriever:
    """PubMed检索器"""
    
    def __init__(self):
        self.max_results = config.max_articles
        
    async def search(self, query: str, max_results: int = None) -> List[PubMedArticle]:
        """执行搜索"""
        if not query:
            return []
            
        max_results = max_results or self.max_results
        
        try:
            # 搜索
            search_handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="relevance"
            )
            search_results = Entrez.read(search_handle)
            pmid_list = search_results["IdList"]
            
            if not pmid_list:
                return []
            
            # 获取详情
            fetch_handle = Entrez.efetch(
                db="pubmed",
                id=",".join(pmid_list),
                retmode="xml"
            )
            
            articles = self._parse_xml(fetch_handle.read())
            return articles
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    def _parse_xml(self, xml_data: str) -> List[PubMedArticle]:
        """解析XML"""
        articles = []
        
        try:
            root = ET.fromstring(xml_data)
            
            for elem in root.findall(".//PubmedArticle"):
                pmid = elem.findtext(".//PMID", "")
                title = elem.findtext(".//ArticleTitle", "")
                abstract = elem.findtext(".//AbstractText", "")
                journal = elem.findtext(".//Journal/Title", "")
                
                # 年份
                year = 0
                year_elem = elem.find(".//PubDate/Year")
                if year_elem is not None:
                    try:
                        year = int(year_elem.text)
                    except:
                        pass
                
                # 作者
                authors = []
                for author in elem.findall(".//Author")[:5]:
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
                
                articles.append(PubMedArticle(
                    pmid=pmid,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    journal=journal,
                    year=year,
                    doi=doi
                ))
                
        except Exception as e:
            print(f"Parse failed: {e}")
        
        return articles
    
    async def search_by_entity(self, entity: Any) -> List[PubMedArticle]:
        """基于实体搜索"""
        parts = []
        
        if entity.disease:
            parts.append(f'"{entity.disease}"')
        if entity.target:
            parts.append(f'"{entity.target}"')
        if entity.therapy:
            parts.append(f'"{entity.therapy}"')
        if entity.drug:
            parts.append(f'"{entity.drug}"')
        
        query = " AND ".join(parts)
        return await self.search(query)