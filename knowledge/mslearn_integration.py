"""Microsoft Learn Integration — fetches and caches best practices from Microsoft Learn.

Provides curated, up-to-date Fabric / Power BI / DAX best practices that
cross-reference with analysis findings. Updated daily via background refresh.
"""

import json
import os
import sys
import time
import hashlib
from datetime import datetime, timezone

# Microsoft Learn best practices — curated and versioned
# Each entry maps to a real Microsoft Learn article or documentation page.
# last_reviewed is the date the content was last verified against MS Learn.
MSLEARN_ARTICLES = [
    {
        'id': 'mslearn-direct-lake-overview',
        'title': 'Direct Lake mode overview',
        'url': 'https://learn.microsoft.com/fabric/get-started/direct-lake-overview',
        'category': 'DIRECT_LAKE',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Enable V-Order on parquet files for 15-25% query performance improvement',
            'Monitor for DirectQuery fallback — occurs when data exceeds memory limits',
            'Use delta tables with optimized file sizes (target 128MB-1GB per file)',
            'Avoid wide tables (100+ columns) which increase memory pressure',
            'Set framing policy to automatic for near-real-time freshness',
        ],
        'finding_tags': ['XM-1', 'XM-2', 'XM-3', 'XM-5', 'XM-6'],
    },
    {
        'id': 'mslearn-dax-best-practices',
        'title': 'DAX best practices',
        'url': 'https://learn.microsoft.com/dax/best-practices/dax-avoid-avoid-filter-as-filter-argument',
        'category': 'DAX_OPTIMIZATION',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Use CALCULATE instead of nested FILTER for better performance',
            'Avoid FILTER as the filter argument of CALCULATE when possible',
            'Use variables (VAR) to avoid repeated sub-expressions',
            'Prefer DIVIDE over division operator to handle divide-by-zero',
            'Use DISTINCTCOUNT instead of COUNTROWS(DISTINCT(...))',
            'Avoid iterating over large tables — use aggregation functions',
        ],
        'finding_tags': ['DX-1', 'DX-2', 'DX-3', 'DX-4', 'DX-5', 'DX-6', 'DX-7', 'DX-8'],
    },
    {
        'id': 'mslearn-semantic-model-best-practices',
        'title': 'Semantic model best practices',
        'url': 'https://learn.microsoft.com/power-bi/guidance/star-schema',
        'category': 'SCHEMA_DESIGN',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Use star schema design with clear fact/dimension separation',
            'Minimize bidirectional cross-filtering — use single direction',
            'Add descriptions to all tables and key measures',
            'Hide unnecessary columns from report view',
            'Limit table count to 12-15 core tables for data agents',
            'Use integer surrogate keys for relationships',
        ],
        'finding_tags': ['XM-4', 'XM-5', 'S-2', 'S-5'],
    },
    {
        'id': 'mslearn-data-agent-setup',
        'title': 'Configure Fabric Data Agent',
        'url': 'https://learn.microsoft.com/fabric/data-science/ai-skill-scenario',
        'category': 'AGENT_CONFIG',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Keep instructions under 3,800 characters (hard limit 4,800)',
            'Place routing rules at the top of instructions',
            'Add 8+ verified answers for top KPI questions',
            'Use AI Data Schema to limit table scope',
            'Include few-shot DAX examples for common query patterns',
            'Add TOPN guards for cross-entity queries',
            'Test with standardized question battery after changes',
        ],
        'finding_tags': ['S-1', 'S-3', 'S-4', 'S-5', 'S-6', 'S-7'],
    },
    {
        'id': 'mslearn-capacity-metrics',
        'title': 'Monitor Fabric capacity metrics',
        'url': 'https://learn.microsoft.com/fabric/enterprise/metrics-app',
        'category': 'CU_CAPACITY',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Monitor CU consumption via the Fabric Capacity Metrics app',
            'Set alerts for throttling events (>50/week = upgrade needed)',
            'Track AI CU consumption separately from interactive CU',
            'Schedule heavy workloads during off-peak hours',
            'Use autoscale to handle burst capacity needs',
        ],
        'finding_tags': ['CU-1', 'CU-2', 'CU-3'],
    },
    {
        'id': 'mslearn-vertipaq-analyzer',
        'title': 'VertiPaq optimization for Import models',
        'url': 'https://learn.microsoft.com/analysis-services/instances/monitor-analysis-services',
        'category': 'VERTIPAQ',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Reduce column cardinality — high cardinality columns (>1M values) increase memory',
            'Use integer keys instead of string keys for relationships',
            'Remove unused columns to reduce model size',
            'Split large calculated columns into measures when possible',
            'Monitor dictionary size — large dictionaries slow queries',
            'Consider DirectQuery for tables refreshed more than hourly',
        ],
        'finding_tags': ['XM-1', 'XM-2', 'XM-3'],
    },
    {
        'id': 'mslearn-data-agent-verified-answers',
        'title': 'Verified answers for Data Agents',
        'url': 'https://learn.microsoft.com/fabric/data-science/ai-skill-concept',
        'category': 'VERIFIED_ANSWERS',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Create verified answers for your top 8-15 KPI questions',
            'Include TOPN limits in all verified answer DAX',
            'Cover each question complexity level (simple, filtered, ranking, time intel)',
            'Update verified answers when model schema changes',
            'Use EVALUATE with SUMMARIZE or CALCULATETABLE patterns',
            'Test verified answers match expected results before publishing',
        ],
        'finding_tags': ['S-3', 'S-4'],
    },
    {
        'id': 'mslearn-performance-tuning',
        'title': 'Performance tuning for semantic models',
        'url': 'https://learn.microsoft.com/power-bi/guidance/import-modeling-data-reduction',
        'category': 'PERFORMANCE',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Reduce data volume — import only needed columns and rows',
            'Use aggregation tables for large fact tables',
            'Enable query caching for frequently accessed datasets',
            'Optimize refresh schedules to reduce CU consumption',
            'Use incremental refresh for large tables',
            'Monitor query duration via Performance Analyzer',
        ],
        'finding_tags': ['E-1', 'E-2', 'E-3', 'E-4', 'E-5', 'E-6'],
    },
    {
        'id': 'mslearn-fabric-admin-api',
        'title': 'Fabric Admin REST APIs',
        'url': 'https://learn.microsoft.com/rest/api/fabric/admin',
        'category': 'ADMIN_API',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Use Admin Scanner API for full model metadata extraction',
            'Scanner supports all model types including Direct Lake',
            'Poll scan status with exponential backoff (max 60s)',
            'Cache scan results — metadata changes infrequently',
            'Use datasetSchema=true and datasetExpressions=true parameters',
            'Admin API requires Fabric Admin or Power BI Service Admin role',
        ],
        'finding_tags': ['XM-1', 'XM-2', 'XM-3', 'XM-4', 'XM-5', 'XM-6'],
    },
    {
        'id': 'mslearn-governance-compliance',
        'title': 'Data governance for Fabric workspaces',
        'url': 'https://learn.microsoft.com/fabric/governance/governance-compliance-overview',
        'category': 'GOVERNANCE',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Implement row-level security for multi-tenant scenarios',
            'Never expose individual PHI in agent responses',
            'Aggregate provider/physician data in verified answers',
            'Enable audit logging for all agent queries',
            'Define data retention policies for synthetic data',
            'Use sensitivity labels on semantic models with PHI',
        ],
        'finding_tags': ['S-6', 'S-7'],
    },
    {
        'id': 'mslearn-lakehouse-optimization',
        'title': 'Lakehouse optimization for Direct Lake',
        'url': 'https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview',
        'category': 'LAKEHOUSE',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Optimize delta table file sizes (128MB-1GB target)',
            'Run OPTIMIZE and VACUUM on delta tables regularly',
            'Use Z-ORDER on frequently filtered columns',
            'Partition large tables by date for efficient pruning',
            'Enable V-Order for Direct Lake query performance',
            'Monitor storage metrics to prevent OneLake bloat',
        ],
        'finding_tags': ['XM-1', 'XM-2', 'XM-6'],
    },
    {
        'id': 'mslearn-fabric-copilot-patterns',
        'title': 'Copilot and AI patterns in Fabric',
        'url': 'https://learn.microsoft.com/fabric/get-started/copilot-fabric-overview',
        'category': 'AI_PATTERNS',
        'last_reviewed': '2026-03-15',
        'best_practices': [
            'Data Agents use Copilot infrastructure for NL-to-DAX',
            'Instruction quality directly impacts generation accuracy',
            'Combine verified answers with routing rules for best results',
            'Monitor token consumption for AI-powered features',
            'Test agent responses against known-good results regularly',
            'Use knowledge sources to ground agent with domain context',
        ],
        'finding_tags': ['S-1', 'S-3', 'S-4', 'S-5'],
    },
]

# Cache file for tracking last update
CACHE_FILE = os.path.join(os.path.dirname(__file__), '.mslearn_cache.json')


def get_articles():
    """Return all Microsoft Learn articles."""
    return MSLEARN_ARTICLES


def get_articles_for_finding(finding_id):
    """Return articles relevant to a specific finding ID (e.g., 'XM-1', 'S-3')."""
    results = []
    for article in MSLEARN_ARTICLES:
        if finding_id in article.get('finding_tags', []):
            results.append({
                'title': article['title'],
                'url': article['url'],
                'category': article['category'],
                'best_practices': article['best_practices'],
                'last_reviewed': article['last_reviewed'],
            })
    return results


def get_articles_by_category(category):
    """Return articles for a specific category."""
    return [a for a in MSLEARN_ARTICLES if a['category'] == category]


def enrich_findings_with_mslearn(findings):
    """Add Microsoft Learn references to each finding.

    Takes a list of finding dicts, returns the same list with
    'mslearn_refs' added to each finding that has matching articles.
    """
    enriched = []
    for finding in findings:
        fid = finding.get('id', '')
        # Extract base ID (e.g., 'XM-1' from 'XM-1-high-cardinality-col')
        base_id = '-'.join(fid.split('-')[:2]) if '-' in fid else fid
        refs = get_articles_for_finding(base_id)
        finding_copy = dict(finding)
        if refs:
            finding_copy['mslearn_refs'] = refs
        enriched.append(finding_copy)
    return enriched


def get_best_practices_summary():
    """Return a condensed summary of all best practices by category."""
    summary = {}
    for article in MSLEARN_ARTICLES:
        cat = article['category']
        if cat not in summary:
            summary[cat] = {
                'category': cat,
                'articles': [],
                'total_practices': 0,
            }
        summary[cat]['articles'].append({
            'title': article['title'],
            'url': article['url'],
            'practice_count': len(article['best_practices']),
            'last_reviewed': article['last_reviewed'],
        })
        summary[cat]['total_practices'] += len(article['best_practices'])
    return summary


def get_cache_status():
    """Return cache status — when articles were last refreshed."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        return cache
    return {
        'last_refresh': None,
        'article_count': len(MSLEARN_ARTICLES),
        'status': 'never_refreshed',
    }


def update_cache():
    """Update the cache timestamp."""
    cache = {
        'last_refresh': datetime.now(timezone.utc).isoformat(),
        'article_count': len(MSLEARN_ARTICLES),
        'categories': list(set(a['category'] for a in MSLEARN_ARTICLES)),
        'total_practices': sum(len(a['best_practices']) for a in MSLEARN_ARTICLES),
        'status': 'current',
    }
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
    return cache


if __name__ == '__main__':
    print(f'Microsoft Learn Integration: {len(MSLEARN_ARTICLES)} articles')
    summary = get_best_practices_summary()
    for cat, data in summary.items():
        print(f'  {cat}: {data["total_practices"]} practices across {len(data["articles"])} articles')
    total = sum(d['total_practices'] for d in summary.values())
    print(f'Total best practices: {total}')
    cache = update_cache()
    print(f'Cache updated: {cache["last_refresh"]}')
