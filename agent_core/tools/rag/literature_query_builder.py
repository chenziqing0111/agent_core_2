# agent_core/tools/rag/literature_query_builder.py

"""
Literature Query Builder - 文献查询构建模块
负责：16种组合的维度定义和查询构建
"""

from typing import Dict, List, Any, Callable


class LiteratureQueryBuilder:
    """文献查询构建器 - 管理16种组合的查询策略"""
    
    def __init__(self):
        self.dimension_configs = self._init_dimension_configs()

    def with_aliases(self, primary, aliases_attr_name, entity, max_num=2):
        """构建带别名的查询项 - 改为实例方法"""
        aliases = getattr(entity, aliases_attr_name, [])
        if aliases and len(aliases) > 0:
            terms = [f'"{primary}"'] + [f'"{a}"' for a in aliases[:max_num]]
            return f"({' OR '.join(terms)})"
        return f'"{primary}"'
    
    def _init_dimension_configs(self) -> Dict[str, Dict]:
        """初始化16种组合的维度配置"""
        return {
           # ========== 单一实体 ==========
        'T': {
            'dimensions': ['structure_function', 'disease_association', 'druggability'],
            'queries': {
                'structure_function': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} structure function pathway mechanism",
                'disease_association': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} disease association pathology",
                'druggability': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} drug target therapeutic potential"
            }
        },
        
        'D': {
            'dimensions': ['pathogenesis', 'therapeutic_targets', 'epidemiology'],
            'queries': {
                'pathogenesis': lambda e: f"{self.with_aliases(e.disease, 'disease_aliases', e)} pathogenesis mechanism etiology",
                'therapeutic_targets': lambda e: f"{self.with_aliases(e.disease, 'disease_aliases', e)} therapeutic targets biomarkers",
                'epidemiology': lambda e: f"{self.with_aliases(e.disease, 'disease_aliases', e)} epidemiology prevalence incidence"
            }
        },
        
        'R': {
            'dimensions': ['mechanism', 'clinical_application', 'advances'],
            'queries': {
                'mechanism': lambda e: f"{self.with_aliases(e.therapy, 'therapy_aliases', e, 1)} mechanism action principle",
                'clinical_application': lambda e: f"{self.with_aliases(e.therapy, 'therapy_aliases', e, 1)} clinical application efficacy",
                'advances': lambda e: f"{self.with_aliases(e.therapy, 'therapy_aliases', e, 1)} advances development innovation"
            }
        },
        
        'M': {
            'dimensions': ['pharmacology', 'efficacy_safety', 'resistance'],
            'queries': {
                'pharmacology': lambda e: f"{self.with_aliases(e.drug, 'drug_aliases', e)} pharmacology pharmacokinetics ADME",
                'efficacy_safety': lambda e: f"{self.with_aliases(e.drug, 'drug_aliases', e)} efficacy safety adverse events",
                'resistance': lambda e: f"{self.with_aliases(e.drug, 'drug_aliases', e)} resistance mechanism combination"
            }
        },
        
        # ========== 双实体组合 ==========
        'TD': {
            'dimensions': ['association', 'mechanism', 'therapeutic_potential'],
            'queries': {
                'association': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} {self.with_aliases(e.disease, 'disease_aliases', e, 1)} association genetic GWAS",
                'mechanism': lambda e: f"{e.target} {e.disease} mechanism pathway pathogenesis",
                'therapeutic_potential': lambda e: f"{e.target} {e.disease} therapeutic target drug potential"
            }
        },
        
        'TR': {
            'dimensions': ['targeting_approach', 'modulation_effects', 'clinical_outcomes'],
            'queries': {
                'targeting_approach': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} {e.therapy} targeting approach strategy",
                'modulation_effects': lambda e: f"{e.target} {e.therapy} modulation inhibition activation",
                'clinical_outcomes': lambda e: f"{e.target} {e.therapy} clinical outcome efficacy"
            }
        },
        
        'TM': {
            'dimensions': ['binding_interaction', 'selectivity', 'therapeutic_window'],
            'queries': {
                'binding_interaction': lambda e: f"{self.with_aliases(e.target, 'target_aliases', e)} {self.with_aliases(e.drug, 'drug_aliases', e)} binding interaction affinity",
                'selectivity': lambda e: f"{e.target} {e.drug} selectivity specificity off-target",
                'therapeutic_window': lambda e: f"{e.target} {e.drug} therapeutic window dose response"
            }
        },
        
        'DR': {
            'dimensions': ['treatment_rationale', 'clinical_efficacy', 'patient_selection'],
            'queries': {
                'treatment_rationale': lambda e: f"{self.with_aliases(e.disease, 'disease_aliases', e, 1)} {e.therapy} rationale mechanism",
                'clinical_efficacy': lambda e: f"{e.disease} {e.therapy} efficacy outcome survival",
                'patient_selection': lambda e: f"{e.disease} {e.therapy} patient selection biomarker"
            }
        },
        
        'DM': {
            'dimensions': ['drug_indication', 'clinical_trials', 'real_world'],
            'queries': {
                'drug_indication': lambda e: f"{self.with_aliases(e.disease, 'disease_aliases', e, 1)} {self.with_aliases(e.drug, 'drug_aliases', e)} indication approval",
                'clinical_trials': lambda e: f"{e.disease} {e.drug} clinical trial phase efficacy",
                'real_world': lambda e: f"{e.disease} {e.drug} real world evidence outcome"
            }
        },
        
        'RM': {
            'dimensions': ['delivery_method', 'drug_compatibility', 'synergy'],
            'queries': {
                'delivery_method': lambda e: f"{e.therapy} {self.with_aliases(e.drug, 'drug_aliases', e)} delivery administration",
                'drug_compatibility': lambda e: f"{e.therapy} {e.drug} compatibility interaction",
                'synergy': lambda e: f"{e.therapy} {e.drug} synergy combination enhancement"
            }
        },
        
        # ========== 三实体组合 ==========
        'TDR': {
            'dimensions': ['precision_targeting', 'clinical_validation', 'future_directions'],
            'queries': {
                'precision_targeting': lambda e: f"{e.target} {e.disease} {e.therapy} precision biomarker-guided",
                'clinical_validation': lambda e: f"{e.target} {e.disease} {e.therapy} clinical validation efficacy",
                'future_directions': lambda e: f"{e.target} {e.disease} {e.therapy} future development optimization"
            }
        },
        
        'TDM': {
            'dimensions': ['mechanistic_efficacy', 'biomarker_stratification', 'resistance_management'],
            'queries': {
                'mechanistic_efficacy': lambda e: f"{e.target} {e.disease} {e.drug} mechanism efficacy",
                'biomarker_stratification': lambda e: f"{e.target} {e.disease} {e.drug} biomarker patient stratification",
                'resistance_management': lambda e: f"{e.target} {e.disease} {e.drug} resistance overcome combination"
            }
        },
        
        'TRM': {
            'dimensions': ['target_modulation', 'drug_optimization', 'delivery_innovation'],
            'queries': {
                'target_modulation': lambda e: f"{e.target} {e.therapy} {e.drug} modulation mechanism",
                'drug_optimization': lambda e: f"{e.target} {e.therapy} {e.drug} optimization improvement",
                'delivery_innovation': lambda e: f"{e.target} {e.therapy} {e.drug} delivery innovation"
            }
        },
        
        'DRM': {
            'dimensions': ['treatment_paradigm', 'clinical_implementation', 'outcome_optimization'],
            'queries': {
                'treatment_paradigm': lambda e: f"{e.disease} {e.therapy} {e.drug} treatment paradigm",
                'clinical_implementation': lambda e: f"{e.disease} {e.therapy} {e.drug} clinical implementation",
                'outcome_optimization': lambda e: f"{e.disease} {e.therapy} {e.drug} outcome optimization"
            }
        },
        
        # ========== 四实体组合 ==========
        'TDRM': {
            'dimensions': ['comprehensive_mechanism', 'clinical_implementation', 'personalized_strategy'],
            'queries': {
                # 四实体组合不用别名，避免过于复杂
                'comprehensive_mechanism': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} mechanism comprehensive",
                'clinical_implementation': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} clinical implementation",
                'personalized_strategy': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} personalized precision"
            }
        },
        
        # ========== 空组合 ==========
        'EMPTY': {
            'dimensions': ['general_overview'],
            'queries': {
                'general_overview': lambda e: "biomedical research clinical therapeutic"
            }
        }
    }
    
    def get_combination_key(self, entity: Any) -> str:
        """
        生成实体组合键
        
        Args:
            entity: 实体对象
            
        Returns:
            组合键字符串（如 'TD', 'TDRM'）
        """
        key = ""
        if getattr(entity, 'target', None):
            key += "T"
        if getattr(entity, 'disease', None):
            key += "D"
        if getattr(entity, 'therapy', None):
            key += "R"
        if getattr(entity, 'drug', None):
            key += "M"
        return key if key else "EMPTY"
    
    def get_dimensions_for_combination(self, entity: Any) -> Dict[str, str]:
        """
        根据实体组合获取对应的维度查询
        
        Args:
            entity: 实体对象
            
        Returns:
            Dict[dimension_name, query_string]
        """
        combo_key = self.get_combination_key(entity)
        config = self.dimension_configs.get(combo_key, self.dimension_configs['EMPTY'])
        
        dimensions = {}
        for dim_name in config['dimensions']:
            if dim_name in config['queries']:
                query_fn = config['queries'][dim_name]
                dimensions[dim_name] = query_fn(entity)
        
        return dimensions
    
    