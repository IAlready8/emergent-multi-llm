"""Tier configuration and constants for Prometheus."""
from __future__ import annotations

TIERS = {
    "free": {
        "price_usd_month": 0,
        "runs_per_period": 10,
        "upload_max_mb": 5,
        "csv_row_limit": 10000,
        "url_fetch_limit": 1,
        "agents": ["Analyzer", "Aggregator", "Classifier"],
        "custom_workflows": False,
        "workflow_storage_limit": 3,
        "provider_mode": "gemini_only",
        "concurrent_runs": 1,
        "history_days": 7,
        "export_json": True,
        "export_pdf": False,
        "connectors": ["paste", "csv", "txt", "md", "json", "url"],
        "rate_limit_runs_per_hour": 5,
        "retries": 1,
        "agent_timeout_sec": 30,
        "run_timeout_sec": 600,
    },
    "pro": {
        "price_usd_month": 29,
        "price_usd_year": 290,
        "runs_per_period": 500,
        "upload_max_mb": 50,
        "csv_row_limit": 250000,
        "url_fetch_limit": 10,
        "agents": ["Analyzer", "Aggregator", "AnomalyDetector", "Classifier", "Synthesizer"],
        "custom_workflows": True,
        "workflow_storage_limit": 100,
        "provider_mode": "per_run",
        "concurrent_runs": 3,
        "history_days": 90,
        "export_json": True,
        "export_pdf": True,
        "connectors": ["paste", "csv", "txt", "md", "json", "url"],
        "rate_limit_runs_per_hour": 100,
        "retries": 2,
        "agent_timeout_sec": 90,
        "run_timeout_sec": 1800,
    },
    "enterprise": {
        "price_usd_month": 199,
        "price_usd_year": 1990,
        "runs_per_period": None,
        "soft_run_limit": 10000,
        "upload_max_mb": 500,
        "csv_row_limit": 2000000,
        "url_fetch_limit": 100,
        "agents": ["Analyzer", "Aggregator", "AnomalyDetector", "Classifier", "Synthesizer"],
        "custom_workflows": True,
        "workflow_storage_limit": None,
        "provider_mode": "per_agent",
        "concurrent_runs": 10,
        "history_days": None,
        "export_json": True,
        "export_pdf": True,
        "connectors": ["paste", "csv", "txt", "md", "json", "url", "postgres_readonly", "s3_readonly"],
        "rate_limit_runs_per_hour": 1000,
        "retries": 3,
        "agent_timeout_sec": 180,
        "run_timeout_sec": 3600,
    },
}

TIER_TO_LOOKUP_KEYS = {
    "pro": {"month": "pro_monthly", "year": "pro_annual"},
    "enterprise": {"month": "enterprise_monthly", "year": "enterprise_annual"},
}

LOOKUP_KEY_TO_TIER = {
    "pro_monthly": ("pro", "month"),
    "pro_annual": ("pro", "year"),
    "enterprise_monthly": ("enterprise", "month"),
    "enterprise_annual": ("enterprise", "year"),
}

AGENT_TYPES = ["Analyzer", "Aggregator", "AnomalyDetector", "Classifier", "Synthesizer"]

AGENT_PROMPTS = {
    "Analyzer": (
        "You are Analyzer. Extract entities, facts, key themes, and summary from the input. "
        "Return concise structured JSON with keys: entities, themes, key_findings, summary, source_excerpts."
    ),
    "Aggregator": (
        "You are Aggregator. Merge structured and unstructured signals from prior agents' outputs. "
        "Return JSON with keys: combined_results, counts, grouped, top_records, missing_fields, data_quality_notes."
    ),
    "AnomalyDetector": (
        "You are AnomalyDetector. Flag outliers, missing data, contradictions, and suspicious patterns. "
        "Return JSON with keys: anomalies (list of {severity, reason, affected, confidence, recommended_action})."
    ),
    "Classifier": (
        "You are Classifier. Assign categories, labels, and confidence scores to input items. "
        "Return JSON with keys: categories, labels (list of {item, label, confidence}), ambiguous, rejected."
    ),
    "Synthesizer": (
        "You are Synthesizer. Produce the final executive report using prior agents' outputs. "
        "Return JSON with keys: executive_summary, key_risks, key_opportunities, recommended_actions, open_issues, final_report."
    ),
}

TEMPLATES = [
    {
        "id": "doc_insight",
        "name": "Document Insight Pipeline",
        "description": "Classify, analyze, and synthesize a document.",
        "agents": [
            {"type": "Analyzer", "provider": "gemini"},
            {"type": "Classifier", "provider": "gemini"},
            {"type": "Synthesizer", "provider": "gemini"},
        ],
    },
    {
        "id": "csv_anomaly",
        "name": "CSV Anomaly & Classification Pipeline",
        "description": "Detect anomalies and classify records in tabular data.",
        "agents": [
            {"type": "Analyzer", "provider": "gemini"},
            {"type": "AnomalyDetector", "provider": "gemini"},
            {"type": "Classifier", "provider": "gemini"},
            {"type": "Synthesizer", "provider": "gemini"},
        ],
    },
    {
        "id": "url_research",
        "name": "URL Research Synthesis",
        "description": "Fetch a URL and synthesize a research briefing.",
        "agents": [
            {"type": "Analyzer", "provider": "gemini"},
            {"type": "Aggregator", "provider": "gemini"},
            {"type": "Synthesizer", "provider": "gemini"},
        ],
    },
]
