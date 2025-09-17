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
    
    def _init_dimension_configs(self) -> Dict[str, Dict]:
        """初始化16种组合的维度配置"""
        return {
            # ========== 单实体组合 ==========
            'T': {
                'dimensions': ['structure_function', 'pathway_regulation', 'clinical_relevance'],
                'queries': {
                    'structure_function': lambda e: f"{e.target} structure function domain active site binding",
                    'pathway_regulation': lambda e: f"{e.target} pathway signaling regulation mechanism cascade",
                    'clinical_relevance': lambda e: f"{e.target} clinical disease therapeutic target drug"
                }
            },
            
            'D': {
                'dimensions': ['pathogenesis', 'biomarkers', 'current_treatment'],
                'queries': {
                    'pathogenesis': lambda e: f"{e.disease} pathogenesis etiology mechanism pathophysiology",
                    'biomarkers': lambda e: f"{e.disease} biomarker diagnostic prognostic marker",
                    'current_treatment': lambda e: f"{e.disease} treatment therapy standard care guideline"
                }
            },
            
            'R': {
                'dimensions': ['mechanism_of_action', 'clinical_applications', 'optimization'],
                'queries': {
                    'mechanism_of_action': lambda e: f"{e.therapy} mechanism action molecular cellular effect",
                    'clinical_applications': lambda e: f"{e.therapy} clinical application indication patient outcome",
                    'optimization': lambda e: f"{e.therapy} optimization improvement combination personalized"
                }
            },
            
            'M': {
                'dimensions': ['pharmacology', 'efficacy_safety', 'resistance'],
                'queries': {
                    'pharmacology': lambda e: f"{e.drug} pharmacology pharmacokinetics pharmacodynamics ADME",
                    'efficacy_safety': lambda e: f"{e.drug} efficacy safety adverse events toxicity",
                    'resistance': lambda e: f"{e.drug} resistance mechanism overcome combination strategy"
                }
            },
            
            # ========== 双实体组合 ==========
            'TD': {
                'dimensions': ['association', 'mechanism', 'therapeutic_potential'],
                'queries': {
                    'association': lambda e: f"{e.target} {e.disease} association genetic GWAS risk variant mutation",
                    'mechanism': lambda e: f"{e.target} {e.disease} mechanism pathway pathogenesis dysfunction",
                    'therapeutic_potential': lambda e: f"{e.target} {e.disease} therapeutic target drug treatment potential"
                }
            },
            
            'TR': {
                'dimensions': ['targeting_approach', 'modulation_effects', 'clinical_outcomes'],
                'queries': {
                    'targeting_approach': lambda e: f"{e.target} {e.therapy} targeting approach strategy selective specific",
                    'modulation_effects': lambda e: f"{e.target} {e.therapy} modulation inhibition activation effect",
                    'clinical_outcomes': lambda e: f"{e.target} {e.therapy} clinical outcome efficacy response patient"
                }
            },
            
            'TM': {
                'dimensions': ['binding_interaction', 'selectivity', 'therapeutic_window'],
                'queries': {
                    'binding_interaction': lambda e: f"{e.target} {e.drug} binding interaction affinity kinetics structure",
                    'selectivity': lambda e: f"{e.target} {e.drug} selectivity specificity off-target",
                    'therapeutic_window': lambda e: f"{e.target} {e.drug} therapeutic window dose response efficacy"
                }
            },
            
            'DR': {
                'dimensions': ['treatment_rationale', 'clinical_efficacy', 'patient_selection'],
                'queries': {
                    'treatment_rationale': lambda e: f"{e.disease} {e.therapy} rationale mechanism basis pathophysiology",
                    'clinical_efficacy': lambda e: f"{e.disease} {e.therapy} efficacy outcome survival response rate",
                    'patient_selection': lambda e: f"{e.disease} {e.therapy} patient selection biomarker stratification"
                }
            },
            
            'DM': {
                'dimensions': ['drug_indication', 'clinical_trials', 'real_world'],
                'queries': {
                    'drug_indication': lambda e: f"{e.disease} {e.drug} indication approval mechanism action",
                    'clinical_trials': lambda e: f"{e.disease} {e.drug} clinical trial phase efficacy safety",
                    'real_world': lambda e: f"{e.disease} {e.drug} real world evidence outcome effectiveness"
                }
            },
            
            'RM': {
                'dimensions': ['delivery_method', 'drug_compatibility', 'synergy'],
                'queries': {
                    'delivery_method': lambda e: f"{e.therapy} {e.drug} delivery administration route formulation",
                    'drug_compatibility': lambda e: f"{e.therapy} {e.drug} compatibility interaction combination",
                    'synergy': lambda e: f"{e.therapy} {e.drug} synergy additive effect enhancement"
                }
            },
            
            # ========== 三实体组合 ==========
            'TDR': {
                'dimensions': ['precision_targeting', 'clinical_validation', 'future_directions'],
                'queries': {
                    'precision_targeting': lambda e: f"{e.target} {e.disease} {e.therapy} precision targeting biomarker-guided",
                    'clinical_validation': lambda e: f"{e.target} {e.disease} {e.therapy} clinical validation trial efficacy",
                    'future_directions': lambda e: f"{e.target} {e.disease} {e.therapy} future combination optimization"
                }
            },
            
            'TDM': {
                'dimensions': ['targeted_therapy', 'biomarker_response', 'resistance_management'],
                'queries': {
                    'targeted_therapy': lambda e: f"{e.target} {e.disease} {e.drug} targeted therapy mechanism",
                    'biomarker_response': lambda e: f"{e.target} {e.disease} {e.drug} biomarker response prediction",
                    'resistance_management': lambda e: f"{e.target} {e.disease} {e.drug} resistance mechanism overcome"
                }
            },
            
            'TRM': {
                'dimensions': ['target_modulation', 'delivery_optimization', 'therapeutic_index'],
                'queries': {
                    'target_modulation': lambda e: f"{e.target} {e.therapy} {e.drug} modulation mechanism selectivity",
                    'delivery_optimization': lambda e: f"{e.target} {e.therapy} {e.drug} delivery optimization targeting",
                    'therapeutic_index': lambda e: f"{e.target} {e.therapy} {e.drug} therapeutic index safety efficacy"
                }
            },
            
            'DRM': {
                'dimensions': ['treatment_paradigm', 'clinical_evidence', 'guidelines'],
                'queries': {
                    'treatment_paradigm': lambda e: f"{e.disease} {e.therapy} {e.drug} treatment paradigm standard",
                    'clinical_evidence': lambda e: f"{e.disease} {e.therapy} {e.drug} clinical evidence trial outcome",
                    'guidelines': lambda e: f"{e.disease} {e.therapy} {e.drug} guideline recommendation consensus"
                }
            },
            
            # ========== 四实体组合 ==========
            'TDRM': {
                'dimensions': ['comprehensive_mechanism', 'clinical_implementation', 'personalized_strategy'],
                'queries': {
                    'comprehensive_mechanism': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} mechanism pathway comprehensive",
                    'clinical_implementation': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} clinical implementation efficacy safety",
                    'personalized_strategy': lambda e: f"{e.target} {e.disease} {e.therapy} {e.drug} personalized precision biomarker stratification"
                }
            },
            
            # ========== 空组合（备用）==========
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
    
    