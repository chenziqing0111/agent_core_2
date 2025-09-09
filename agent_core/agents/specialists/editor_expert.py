# agent_core/agents/editor_agent.py
"""
Editor Agent - 整合多个Agent结果生成专业HTML报告
"""

import json
import re
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ============ 1. Agent类型定义 ============

class AgentType:
    """预定义的Agent类型"""
    LITERATURE = "literature"  # 文献调研
    PATENT = "patent"          # 专利分析
    CLINICAL = "clinical"      # 临床研究
    MARKET = "market"          # 市场分析
    TECHNICAL = "technical"    # 技术分析
    COMPETITOR = "competitor"  # 竞争对手
    REGULATION = "regulation"  # 法规政策
    FINANCIAL = "financial"    # 财务分析
    CUSTOM = "custom"          # 自定义

# Agent显示名称映射
AGENT_DISPLAY_NAMES = {
    AgentType.LITERATURE: "文献调研",
    AgentType.PATENT: "专利分析", 
    AgentType.CLINICAL: "临床研究",
    AgentType.MARKET: "市场分析",
    AgentType.TECHNICAL: "技术分析",
    AgentType.COMPETITOR: "竞争分析",
    AgentType.REGULATION: "法规政策",
    AgentType.FINANCIAL: "财务分析",
    AgentType.CUSTOM: "其他分析"
}

@dataclass
class EditorConfig:
    """Editor配置"""
    api_key: str = "sk-9b3ad78d6d51431c90091b575072e62f"
    base_url: str = "https://api.deepseek.com"
    company_name: str = "益杰立科"
    parallel_processing: bool = True
    max_workers: int = 5
    timeout: int = 30

# ============ 2. 优化的报告模板 ============

class ProfessionalReportTemplate:
    """专业报告模板 - 黑白深蓝配色"""
    
    @staticmethod
    def get_css() -> str:
        """专业的CSS样式 - 黑白深蓝主题"""
        return """
        /* 全局样式重置 */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            /* 主题色 - 黑白深蓝 */
            --primary: #1e3a8a;
            --primary-dark: #1e293b;
            --primary-light: #3b82f6;
            --secondary: #64748b;
            --accent: #60a5fa;
            
            /* 背景色 */
            --bg-main: #f8fafc;
            --card-bg: #ffffff;
            --sidebar-bg: #1e293b;
            
            /* 文字颜色 */
            --text-primary: #1e293b;
            --text-secondary: #475569;
            --text-light: #94a3b8;
            --text-white: #ffffff;
            
            /* 边框和阴影 */
            --border-light: #e2e8f0;
            --shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            
            /* 动画 */
            --transition: all 0.2s ease;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 
                         'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-main);
            color: var(--text-primary);
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }
        
        /* 顶部品牌栏 */
        .brand-bar {
            background: var(--card-bg);
            box-shadow: var(--shadow-md);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            height: 64px;
            border-bottom: 1px solid var(--border-light);
        }
        
        .brand-logo {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .logo-icon {
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }
        
        .brand-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .report-actions {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        .report-info {
            display: flex;
            gap: 20px;
            align-items: center;
            margin-right: 20px;
        }
        
        .report-info-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        .report-info-item i {
            color: var(--primary);
            font-size: 12px;
        }
        
        /* 操作按钮 */
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: var(--transition);
            border: none;
            font-size: 14px;
        }
        
        .btn-primary {
            background: var(--primary);
            color: white;
        }
        
        .btn-primary:hover {
            background: var(--primary-dark);
        }
        
        .btn-outline {
            background: transparent;
            border: 1px solid var(--border-light);
            color: var(--text-secondary);
        }
        
        .btn-outline:hover {
            background: var(--bg-main);
            border-color: var(--primary);
            color: var(--primary);
        }
        
        /* 主容器布局 - 满屏居中 */
        .main-wrapper {
            display: flex;
            margin-top: 64px;
            height: calc(100vh - 64px);
            width: 100%;
            max-width: 100%;
            margin-left: auto;
            margin-right: auto;
        }
        
        /* 侧边栏 */
        .sidebar {
            width: 260px;
            background: var(--sidebar-bg);
            overflow-y: auto;
            flex-shrink: 0;
            position: fixed;
            left: 0;
            top: 64px;
            bottom: 0;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            z-index: 999;
        }
        
        .sidebar::-webkit-scrollbar {
            width: 6px;
        }
        
        .sidebar::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        
        .sidebar-header {
            color: var(--text-white);
            padding: 24px 20px 20px;
            font-size: 16px;
            font-weight: 600;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 16px;
        }
        
        .nav-section {
            margin-bottom: 24px;
        }
        
        .nav-section-title {
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 0 20px 8px;
            font-weight: 600;
        }
        
        /* 导航项和子导航 */
        .nav-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            color: rgba(255, 255, 255, 0.8);
            cursor: pointer;
            transition: var(--transition);
            position: relative;
            font-size: 14px;
        }
        
        .nav-item:hover {
            background: rgba(255, 255, 255, 0.05);
            color: white;
        }
        
        .nav-item.active {
            background: rgba(59, 130, 246, 0.1);
            color: white;
        }
        
        .nav-item.active::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: var(--primary-light);
        }
        
        .nav-item i {
            width: 16px;
            text-align: center;
            font-size: 14px;
        }
        
        /* 子导航 */
        .nav-subitems {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .nav-item.active + .nav-subitems,
        .nav-item.expanded + .nav-subitems {
            max-height: 500px;
        }
        
        .nav-subitem {
            padding: 8px 20px 8px 46px;
            color: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            font-size: 13px;
            transition: var(--transition);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .nav-subitem:hover {
            color: rgba(255, 255, 255, 0.9);
            background: rgba(255, 255, 255, 0.03);
        }
        
        .nav-subitem.active {
            color: var(--accent);
            background: rgba(59, 130, 246, 0.05);
        }
        
        /* 主内容区域 - 满屏适配 */
        .main-content {
            flex: 1;
            margin-left: 260px;
            padding: 32px 60px;
            overflow-y: auto;
            width: calc(100% - 260px);
            max-width: 1400px;
            margin-right: auto;
        }
        
        .main-content::-webkit-scrollbar {
            width: 8px;
        }
        
        .main-content::-webkit-scrollbar-thumb {
            background: var(--secondary);
            border-radius: 4px;
        }
        
        /* 内容区块 */
        .section {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 32px;
            margin-bottom: 24px;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-light);
        }
        
        .section-header {
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid var(--border-light);
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .section-header i {
            width: 40px;
            height: 40px;
            background: var(--bg-main);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--primary);
            font-size: 20px;
        }
        
        /* 不同Agent类型的配色 */
        .section.literature .section-header i { 
            background: #f3e8ff; 
            color: #7c3aed; 
        }
        .section.patent .section-header i { 
            background: #fce7f3; 
            color: #ec4899; 
        }
        .section.clinical .section-header i { 
            background: #dcfce7; 
            color: #16a34a; 
        }
        .section.market .section-header i { 
            background: #fed7aa; 
            color: #ea580c; 
        }
        .section.technical .section-header i { 
            background: #dbeafe; 
            color: #2563eb; 
        }
        .section.competitor .section-header i { 
            background: #fee2e2; 
            color: #dc2626; 
        }
        .section.regulation .section-header i { 
            background: #e9d5ff; 
            color: #9333ea; 
        }
        .section.financial .section-header i { 
            background: #ccfbf1; 
            color: #0d9488; 
        }
        
        .section-header h2 {
            color: var(--text-primary);
            font-size: 24px;
            font-weight: 600;
            margin: 0;
        }
        
        /* Agent内容样式 - 简洁为主 */
        .agent-content {
            color: var(--text-primary);
            line-height: 1.8;
        }
        
        .agent-content h3 {
            color: var(--text-primary);
            font-size: 20px;
            margin: 28px 0 16px;
            font-weight: 600;
        }
        
        .agent-content h4 {
            color: var(--text-primary);
            font-size: 16px;
            margin: 20px 0 12px;
            font-weight: 600;
        }
        
        .agent-content p {
            color: var(--text-secondary);
            margin-bottom: 16px;
            text-align: justify;
        }
        
        .agent-content ul, .agent-content ol {
            margin: 16px 0 16px 24px;
            color: var(--text-secondary);
        }
        
        .agent-content li {
            margin-bottom: 8px;
        }
        
        /* 统计卡片 - 添加动画效果 */
        .stat-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin: 24px 0;
        }
        
        .stat-card {
            background: var(--bg-main);
            border-radius: 8px;
            padding: 20px;
            border: 1px solid var(--border-light);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
            border-color: var(--primary-light);
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--primary-light), transparent);
            animation: shimmer 3s infinite;
        }
        
        @keyframes shimmer {
            0% { left: -100%; }
            50% { left: 100%; }
            100% { left: 100%; }
        }
        
        .stat-title {
            font-size: 12px;
            color: var(--text-light);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .stat-value {
            font-size: 32px;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 4px;
            animation: countUp 1s ease-out;
        }
        
        @keyframes countUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .stat-info {
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        /* 信息卡片 - 更清晰的配色 */
        .info-card {
            background: #f0f9ff;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            border-left: 4px solid var(--primary);
            border: 1px solid #bfdbfe;
        }
        
        .info-card-header {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
            color: var(--primary-dark);
        }
        
        .info-card-content {
            color: var(--text-secondary);
            line-height: 1.6;
        }
        
        /* 表格样式 - 清晰的表头 */
        .agent-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border: 1px solid var(--border-light);
        }
        
        .agent-content thead {
            background: var(--bg-main);
        }
        
        .agent-content th {
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: var(--text-primary);
            border-bottom: 2px solid var(--border-light);
            font-size: 14px;
        }
        
        .agent-content td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-light);
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        .agent-content tbody tr:hover {
            background: var(--bg-main);
        }
        
        .agent-content tbody tr:last-child td {
            border-bottom: none;
        }
        
        /* 时间线 - 仅在需要时使用 */
        .timeline {
            position: relative;
            padding: 20px 0;
            margin: 24px 0;
        }
        
        .timeline::before {
            content: '';
            position: absolute;
            left: 16px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: var(--border-light);
        }
        
        .timeline-item {
            position: relative;
            padding-left: 40px;
            margin-bottom: 24px;
        }
        
        .timeline-item::before {
            content: '';
            position: absolute;
            left: 11px;
            top: 4px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--primary);
            border: 2px solid white;
            box-shadow: 0 0 0 4px var(--bg-main);
        }
        
        .timeline-date {
            color: var(--primary);
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 14px;
        }
        
        .timeline-content {
            background: var(--bg-main);
            padding: 12px 16px;
            border-radius: 6px;
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        /* 进度条 */
        .progress-bar {
            width: 100%;
            height: 6px;
            background: var(--border-light);
            border-radius: 3px;
            overflow: hidden;
            margin: 12px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--primary);
            transition: width 0.3s ease;
        }
        
        /* SWOT分析网格 - 仅用于商业分析 */
        .swot-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin: 24px 0;
        }
        
        .swot-card {
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-light);
        }
        
        .swot-card.strengths {
            background: #dcfce7;
            border-color: #86efac;
        }
        
        .swot-card.weaknesses {
            background: #fed7aa;
            border-color: #fdba74;
        }
        
        .swot-card.opportunities {
            background: #dbeafe;
            border-color: #93c5fd;
        }
        
        .swot-card.threats {
            background: #fee2e2;
            border-color: #fca5a5;
        }
        
        .swot-card h4 {
            color: var(--text-primary);
            margin-bottom: 12px;
            font-size: 16px;
        }
        
        .swot-card p, .swot-card ul {
            color: var(--text-secondary);
            font-size: 14px;
        }
        
        /* 其他推荐组件 */
        
        /* 关键发现卡片 */
        .key-finding {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-left: 4px solid #f59e0b;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            position: relative;
        }
        
        .key-finding::before {
            content: '💡';
            position: absolute;
            top: 20px;
            right: 20px;
            font-size: 24px;
            opacity: 0.5;
        }
        
        .key-finding h4 {
            color: #92400e;
            margin-bottom: 10px;
            font-weight: 600;
        }
        
        .key-finding p {
            color: #78350f;
        }
        
        /* 风险提示 */
        .risk-alert {
            background: #fee2e2;
            border-left: 4px solid #dc2626;
            padding: 16px 20px;
            margin: 20px 0;
            border-radius: 8px;
        }
        
        .risk-alert h4 {
            color: #991b1b;
            margin-bottom: 8px;
            font-size: 16px;
        }
        
        .risk-alert p {
            color: #7f1d1d;
            font-size: 14px;
        }
        
        /* 对比表格 */
        .comparison-table {
            width: 100%;
            margin: 20px 0;
            border-collapse: separate;
            border-spacing: 0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
        }
        
        .comparison-table thead tr {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
        }
        
        .comparison-table th {
            padding: 14px;
            color: white;
            font-weight: 600;
            text-align: left;
        }
        
        .comparison-table tbody tr:nth-child(odd) {
            background: var(--bg-main);
        }
        
        .comparison-table tbody tr:nth-child(even) {
            background: white;
        }
        
        .comparison-table td {
            padding: 12px 14px;
            color: var(--text-secondary);
        }
        
        .comparison-table tbody tr:hover {
            background: #f0f9ff;
        }
        
        /* 里程碑 */
        .milestone {
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 16px;
            background: var(--bg-main);
            border-radius: 8px;
            margin: 16px 0;
            border: 1px solid var(--border-light);
        }
        
        .milestone-icon {
            width: 48px;
            height: 48px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            flex-shrink: 0;
        }
        
        .milestone-content {
            flex: 1;
        }
        
        .milestone-date {
            font-size: 12px;
            color: var(--text-light);
            margin-bottom: 4px;
        }
        
        .milestone-title {
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }
        
        .milestone-desc {
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        /* 响应式设计 */
        @media (max-width: 1024px) {
            .sidebar {
                width: 220px;
            }
            
            .main-content {
                margin-left: 220px;
            }
        }
        
        @media (max-width: 768px) {
            .brand-bar {
                padding: 12px 16px;
            }
            
            .report-info {
                display: none;
            }
            
            .sidebar {
                position: static;
                width: 100%;
                height: auto;
                max-height: 200px;
            }
            
            .main-content {
                margin-left: 0;
                padding: 20px;
            }
            
            .stat-cards {
                grid-template-columns: 1fr;
            }
            
            .swot-grid {
                grid-template-columns: 1fr;
            }
        }
        
        /* 打印样式 */
        @media print {
            .sidebar, .brand-bar {
                display: none;
            }
            
            .main-wrapper {
                margin-top: 0;
            }
            
            .main-content {
                margin-left: 0;
                padding: 0;
                max-width: 100%;
            }
            
            .section {
                box-shadow: none;
                border: 1px solid #ddd;
                page-break-inside: avoid;
            }
        }
        """
    
    @staticmethod
    def get_html(title: str, company: str, nav_items: List[Dict], sections_html: str, 
                 target: str = "综合分析", analyst: str = "AI分析团队") -> str:
        """生成完整HTML"""
        
        # 生成导航 - 不包含分组标题
        nav_html = ""
        for item in nav_items:
            nav_html += f'''
                <div class="nav-item" data-target="{item["id"]}">
                    <i class="fas {item.get("icon", "fa-file")}"></i>
                    <span>{item["name"]}</span>
                </div>
                <div class="nav-subitems" id="sub-{item["id"]}"></div>
            '''
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | {company}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>{ProfessionalReportTemplate.get_css()}</style>
</head>
<body>
    <!-- 顶部品牌栏 -->
    <div class="brand-bar">
        <div class="brand-logo">
            <div class="logo-icon">
                <i class="fas fa-chart-line"></i>
            </div>
            <div class="brand-title">{company} | 智能分析系统</div>
        </div>
        <div class="report-actions">
            <div class="report-info">
                <div class="report-info-item">
                    <i class="fas fa-bullseye"></i>
                    <span>{target}</span>
                </div>
                <div class="report-info-item">
                    <i class="fas fa-calendar"></i>
                    <span>{current_time}</span>
                </div>
            </div>
            <button class="btn btn-outline" onclick="window.print()">
                <i class="fas fa-print"></i> 打印
            </button>
            <button class="btn btn-primary" onclick="saveReport()">
                <i class="fas fa-download"></i> 保存报告
            </button>
        </div>
    </div>
    
    <div class="main-wrapper">
        <!-- 左侧导航栏 -->
        <div class="sidebar">
            <div class="sidebar-header">
                <i class="fas fa-list"></i> {title}
            </div>
            {nav_html}
        </div>
        
        <!-- 主内容区域 -->
        <div class="main-content">
            {sections_html}
        </div>
    </div>
    
    <script>
        // 导航点击事件和子标题生成
        document.addEventListener('DOMContentLoaded', function() {{
            const navItems = document.querySelectorAll('.nav-item');
            
            // 生成子标题导航
            function generateSubNav() {{
                document.querySelectorAll('.section').forEach(section => {{
                    const sectionId = section.getAttribute('id');
                    const subNavContainer = document.getElementById('sub-' + sectionId);
                    if (subNavContainer) {{
                        const headers = section.querySelectorAll('h3');
                        let subNavHtml = '';
                        headers.forEach((header, index) => {{
                            const headerId = sectionId + '-h3-' + index;
                            header.setAttribute('id', headerId);
                            const headerText = header.textContent.substring(0, 30) + (header.textContent.length > 30 ? '...' : '');
                            subNavHtml += `<div class="nav-subitem" data-target="${{headerId}}">${{headerText}}</div>`;
                        }});
                        subNavContainer.innerHTML = subNavHtml;
                    }}
                }});
                
                // 子标题点击事件
                document.querySelectorAll('.nav-subitem').forEach(item => {{
                    item.addEventListener('click', function(e) {{
                        e.stopPropagation();
                        const targetId = this.getAttribute('data-target');
                        const targetElement = document.getElementById(targetId);
                        if (targetElement) {{
                            targetElement.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                            
                            // 更新活动状态
                            document.querySelectorAll('.nav-subitem').forEach(sub => sub.classList.remove('active'));
                            this.classList.add('active');
                        }}
                    }});
                }});
            }}
            
            // 初始化子导航
            generateSubNav();
            
            // 主导航点击事件
            navItems.forEach(item => {{
                item.addEventListener('click', function() {{
                    navItems.forEach(nav => {{
                        nav.classList.remove('active');
                        nav.classList.remove('expanded');
                    }});
                    this.classList.add('active');
                    this.classList.add('expanded');
                    
                    const targetId = this.getAttribute('data-target');
                    const targetSection = document.getElementById(targetId);
                    
                    if (targetSection) {{
                        targetSection.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                    }}
                }});
            }});
            
            // 滚动监听
            const observerOptions = {{
                root: null,
                rootMargin: '-100px 0px -70% 0px',
                threshold: 0
            }};
            
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        const id = entry.target.getAttribute('id');
                        navItems.forEach(item => {{
                            item.classList.remove('active');
                            if (item.getAttribute('data-target') === id) {{
                                item.classList.add('active');
                                item.classList.add('expanded');
                            }}
                        }});
                    }}
                }});
            }}, observerOptions);
            
            document.querySelectorAll('.section').forEach(section => {{
                observer.observe(section);
            }});
            
            // 激活第一个导航项
            if (navItems.length > 0) {{
                navItems[0].classList.add('active');
                navItems[0].classList.add('expanded');
            }}
        }});
        
        // 保存报告
        function saveReport() {{
            const element = document.documentElement;
            const filename = '{title}_{target}_' + new Date().toISOString().slice(0,10) + '.html';
            const blob = new Blob([element.outerHTML], {{type: 'text/html'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>"""

# ============ 3. Agent处理器 - 优化提示词 ============

class AgentProcessor:
    """处理单个Agent结果"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
    
    def process_agent_data(self, agent_type: str, agent_data: str) -> str:
        """处理单个Agent的数据 - 减少组件使用"""
        
        # 根据Agent类型定制prompt
        agent_prompts = {
            AgentType.LITERATURE: "分析文献调研结果，重点关注研究趋势、关键发现、技术进展",
            AgentType.PATENT: "分析专利数据，重点关注技术布局、创新点、专利壁垒",
            AgentType.CLINICAL: "分析临床研究数据，重点关注试验结果、安全性、有效性",
            AgentType.MARKET: "分析市场数据，重点关注市场规模、增长趋势、竞争格局",
            AgentType.TECHNICAL: "分析技术内容，重点关注技术原理、创新性、可行性",
            AgentType.COMPETITOR: "分析竞争对手信息，重点关注优劣势对比、市场策略",
            AgentType.REGULATION: "分析法规政策，重点关注合规要求、政策影响",
            AgentType.FINANCIAL: "分析财务数据，重点关注关键指标、投资价值"
        }
        
        specific_instruction = agent_prompts.get(agent_type, "分析数据并生成结构化报告")
        
        # 市场分析特殊处理
        swot_instruction = ""
        if agent_type == AgentType.MARKET:
            swot_instruction = """
   - SWOT分析（仅用于市场分析部分）：
     <div class="swot-grid">
       <div class="swot-card strengths">
         <h4>优势 Strengths</h4>
         <p>内容</p>
       </div>
       <div class="swot-card weaknesses">
         <h4>劣势 Weaknesses</h4>
         <p>内容</p>
       </div>
       <div class="swot-card opportunities">
         <h4>机会 Opportunities</h4>
         <p>内容</p>
       </div>
       <div class="swot-card threats">
         <h4>威胁 Threats</h4>
         <p>内容</p>
       </div>
     </div>
"""
        
        prompt = f"""请{specific_instruction}，并生成HTML格式的分析报告。

要求：
1. 直接输出HTML内容，不要```标记,重要：只能输出内容片段，严禁包含 <!DOCTYPE>、<html>、</html>、<head>、</head>、<body>、</body> 标签。
2. 以文字段落为主，适度使用HTML结构：
   - 主要使用 <h3>、<h4> 作为标题（标题要简洁明了）
   - 正文使用 <p> 段落
   - 列表使用 <ul> 或 <ol>
   - 表格使用 <table class="comparison-table">，确保表头清晰
   
3. 可选组件（适度使用）：
   - 关键指标（仅用于最重要的3-4个数据，会有动画效果）：
     <div class="stat-cards">
       <div class="stat-card">
         <div class="stat-title">指标名称</div>
         <div class="stat-value">数值</div>
         <div class="stat-info">说明</div>
       </div>
     </div>
   
   - 重要提示：
     <div class="info-card">
       <div class="info-card-header">标题</div>
       <div class="info-card-content">内容</div>
     </div>
   
   - 关键发现（重要结论）：
     <div class="key-finding">
       <h4>标题</h4>
       <p>内容</p>
     </div>
   
   - 风险提示：
     <div class="risk-alert">
       <h4>风险标题</h4>
       <p>风险说明</p>
     </div>
   
   - 里程碑事件：
     <div class="milestone">
       <div class="milestone-icon">📍</div>
       <div class="milestone-content">
         <div class="milestone-date">日期</div>
         <div class="milestone-title">事件标题</div>
         <div class="milestone-desc">事件描述</div>
       </div>
     </div>
   
   - 时间线（仅在需要展示时间顺序时）：
     <div class="timeline">
       <div class="timeline-item">
         <div class="timeline-date">日期</div>
         <div class="timeline-content">内容</div>
       </div>
     </div>
{swot_instruction}
4. 内容要专业、结构清晰、以文字叙述为主
5. 生成的<h3>标题要适合作为导航子标题显示

数据内容：
{agent_data[:4000]}

直接输出HTML："""
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": f"你是一个专业的{AGENT_DISPLAY_NAMES.get(agent_type, '数据')}分析专家。生成专业的文字报告，适度使用可视化组件。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            html = response.choices[0].message.content
            
            # 清理markdown标记
            html = re.sub(r'^```html?\s*\n?', '', html, flags=re.MULTILINE)
            html = re.sub(r'\n?```\s*$', '', html, flags=re.MULTILINE)
            
            return html
            
        except Exception as e:
            return f'<div class="info-card"><div class="info-card-header">处理失败</div><div class="info-card-content">{str(e)}</div></div>'

# ============ 4. 主报告生成器 ============
class EditorAgent:
    def __init__(self, config: Optional[EditorConfig] = None):
        self.config = config or EditorConfig()
        self.processor = AgentProcessor(self.config.api_key)  # 只传api_key，不传base_url
        logger.info("EditorAgent initialized")
    
    def generate_report(self, 
                       agents_results: Dict[str, Any],
                       gene_target: str,
                       title: Optional[str] = None) -> str:
        """生成基于多个Agent结果的报告"""
        
        if not title:
            title = f"{gene_target}靶点调研报告"
            
        logger.info(f"开始生成报告，共 {len(agents_results)} 个Agent模块...")
        print(f"开始生成报告，共 {len(agents_results)} 个Agent模块...")
        start_time = time.time()
        
        # 转换数据格式
        agents_data = self._convert_agent_results(agents_results)
        
        # 准备导航项
        nav_items = []
        icon_map = {
            AgentType.LITERATURE: "fa-book",
            AgentType.PATENT: "fa-lightbulb",
            AgentType.CLINICAL: "fa-stethoscope",
            AgentType.MARKET: "fa-chart-line",
            AgentType.TECHNICAL: "fa-cogs",
            AgentType.COMPETITOR: "fa-chess",
            AgentType.REGULATION: "fa-gavel",
            AgentType.FINANCIAL: "fa-dollar-sign"
        }
        
        for agent_type in agents_data.keys():
            nav_items.append({
                'id': f'section-{agent_type}',
                'name': AGENT_DISPLAY_NAMES.get(agent_type, agent_type),
                'icon': icon_map.get(agent_type, "fa-file")
            })
        
        # 处理各个Agent的数据
        if self.config.parallel_processing:
            sections_html = self._process_parallel(agents_data)
        else:
            sections_html = self._process_sequential(agents_data)
        
        # 生成最终HTML
        final_html = ProfessionalReportTemplate.get_html(
            title=title,
            company=self.config.company_name,
            nav_items=nav_items,
            sections_html=sections_html,
            target=gene_target
        )
        
        elapsed = time.time() - start_time
        logger.info(f"✅ 报告生成完成！用时: {elapsed:.2f}秒")
        
        return final_html
    
    def _convert_agent_results(self, agents_results: Dict[str, Any]) -> Dict[str, str]:
        """转换Agent结果为字符串格式"""
        converted = {}
        for agent_type, result in agents_results.items():
            if isinstance(result, dict):
                converted[agent_type] = json.dumps(result, ensure_ascii=False, indent=2)
            elif isinstance(result, str):
                converted[agent_type] = result
            else:
                converted[agent_type] = str(result)
        return converted
    
    def _process_parallel(self, agents_data: Dict[str, str]) -> str:
        """并行处理所有Agent数据"""
        sections = {}
        
        with ThreadPoolExecutor(max_workers=min(5, len(agents_data))) as executor:
            future_to_agent = {
                executor.submit(self.processor.process_agent_data, agent_type, data): agent_type
                for agent_type, data in agents_data.items()
            }
            
            for future in as_completed(future_to_agent):
                agent_type = future_to_agent[future]
                try:
                    html_content = future.result(timeout=30)
                    sections[agent_type] = html_content
                    logger.info(f"✓ 完成: {AGENT_DISPLAY_NAMES.get(agent_type, agent_type)}")
                except Exception as e:
                    logger.error(f"✗ 失败: {AGENT_DISPLAY_NAMES.get(agent_type, agent_type)} - {e}")
                    sections[agent_type] = f'<div class="info-card"><div class="info-card-header">生成失败</div><div class="info-card-content">{str(e)}</div></div>'
        
        return self._assemble_sections(agents_data.keys(), sections)
    
    def _process_sequential(self, agents_data: Dict[str, str]) -> str:
        """顺序处理所有Agent数据"""
        sections = {}
        
        for agent_type, data in agents_data.items():
            agent_name = AGENT_DISPLAY_NAMES.get(agent_type, agent_type)
            logger.info(f"处理: {agent_name}...")
            
            try:
                html_content = self.processor.process_agent_data(agent_type, data)
                sections[agent_type] = html_content
            except Exception as e:
                logger.error(f"处理失败: {e}")
                sections[agent_type] = f'<div class="info-card"><div class="info-card-header">生成失败</div><div class="info-card-content">{str(e)}</div></div>'
        
        return self._assemble_sections(agents_data.keys(), sections)
    
    def _assemble_sections(self, agent_types, sections: Dict[str, str]) -> str:
        """组装HTML部分"""
        html_parts = []
        icon_map = {
            AgentType.LITERATURE: "fa-book",
            AgentType.PATENT: "fa-lightbulb",
            AgentType.CLINICAL: "fa-stethoscope",
            AgentType.MARKET: "fa-chart-line",
            AgentType.TECHNICAL: "fa-cogs",
            AgentType.COMPETITOR: "fa-chess",
            AgentType.REGULATION: "fa-gavel",
            AgentType.FINANCIAL: "fa-dollar-sign"
        }
        
        for agent_type in agent_types:
            agent_name = AGENT_DISPLAY_NAMES.get(agent_type, agent_type)
            icon = icon_map.get(agent_type, "fa-file")
            
            html_parts.append(f"""
            <div class="section {agent_type}" id="section-{agent_type}">
                <div class="section-header">
                    <i class="fas {icon}"></i>
                    <h2>{agent_name}</h2>
                </div>
                <div class="agent-content">
                    {sections.get(agent_type, '')}
                </div>
            </div>
            """)
        
        return '\n'.join(html_parts)
    
    def save_report(self, html_content: str, filename: str = None, gene_target: str = None):
        """保存报告到文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            gene_name = gene_target or "report"
            filename = f"{gene_name}_report_{timestamp}.html"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Report saved to {filename}")
        return filename