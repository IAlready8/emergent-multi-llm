"""Server-side HTML -> PDF via WeasyPrint. Includes secret masking."""
from __future__ import annotations

import json
import re
from datetime import datetime

from jinja2 import Template
from weasyprint import HTML

SECRET_PATTERNS = [
    re.compile(r"(sk_[A-Za-z0-9_-]{10,})"),
    re.compile(r"(re_[A-Za-z0-9_-]{10,})"),
    re.compile(r"(pk_[A-Za-z0-9_-]{10,})"),
    re.compile(r"(whsec_[A-Za-z0-9_-]{10,})"),
    re.compile(r"(sk-emergent-[A-Za-z0-9]+)"),
]


def _mask(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def _try_json(text: str):
    if not text:
        return None
    m = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    candidate = m.group(1) if m else text
    try:
        return json.loads(candidate)
    except Exception:
        return None


TEMPLATE = Template("""
<!doctype html>
<html><head><meta charset="utf-8"><title>Prometheus Run Report</title>
<style>
  @page { size: A4; margin: 20mm; }
  body { font-family: 'Helvetica', 'Arial', sans-serif; color: #111; font-size: 11px; }
  h1 { color: #f59e0b; border-bottom: 2px solid #f59e0b; padding-bottom: 6px; }
  h2 { color: #18181b; border-bottom: 1px solid #e4e4e7; padding-bottom: 4px; margin-top: 24px; }
  .meta { color: #52525b; font-size: 10px; }
  .agent-card { background: #fafafa; border: 1px solid #e4e4e7; padding: 10px; margin: 8px 0; }
  pre { background: #18181b; color: #fafafa; padding: 10px; font-size: 9px; white-space: pre-wrap; word-break: break-word; font-family: 'Courier New', monospace; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 10px; }
  th, td { border: 1px solid #e4e4e7; padding: 6px; text-align: left; }
  th { background: #f4f4f5; }
  .cover { text-align: center; padding: 60px 0; }
  .cover h1 { border: none; font-size: 32px; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 10px; background: #f4f4f5; font-size: 9px; }
</style></head><body>

<div class="cover">
  <h1>PROMETHEUS</h1>
  <p style="font-size: 18px">Multi-Agent Run Report</p>
  <p class="meta">Run ID: {{ run.run_id }}</p>
  <p class="meta">Created: {{ run.created_at }}</p>
  <p class="meta">User: {{ user_email }} · Tier: {{ tier }}</p>
</div>

<h2>Input Summary</h2>
<table>
  <tr><th>Input Type</th><td>{{ run.input_type }}</td></tr>
  <tr><th>Character Count</th><td>{{ char_count }}</td></tr>
  {% if run.file_names %}<tr><th>Files</th><td>{{ run.file_names|join(', ') }}</td></tr>{% endif %}
  {% if run.url_list %}<tr><th>URLs</th><td>{{ run.url_list|join(', ') }}</td></tr>{% endif %}
</table>

<h2>Workflow</h2>
<table>
  <tr><th>Agent</th><th>Provider</th><th>Status</th></tr>
  {% for a in run.agents %}
  <tr><td>{{ a.type }}</td><td>{{ a.provider }}</td><td><span class="pill">{{ a.status or 'completed' }}</span></td></tr>
  {% endfor %}
</table>

{% for a in run.agents %}
<h2>{{ a.type }} Output</h2>
<div class="agent-card">
  {% set parsed = agent_json.get(a.type) %}
  {% if parsed %}
    <pre>{{ parsed_json_str[a.type] }}</pre>
  {% else %}
    <pre>{{ agent_outputs.get(a.type, '(no output)') }}</pre>
  {% endif %}
</div>
{% endfor %}

<h2>System Appendix</h2>
<table>
  <tr><th>Started</th><td>{{ run.started_at or '-' }}</td></tr>
  <tr><th>Ended</th><td>{{ run.ended_at or '-' }}</td></tr>
  <tr><th>Status</th><td>{{ run.status }}</td></tr>
</table>

</body></html>
""")


def generate_pdf(run: dict, user_email: str, tier: str) -> bytes:
    agent_outputs = {k: _mask(v or "") for k, v in (run.get("agent_outputs") or {}).items()}
    agent_json = {}
    parsed_json_str = {}
    for k, v in agent_outputs.items():
        parsed = _try_json(v)
        if parsed is not None:
            agent_json[k] = parsed
            parsed_json_str[k] = json.dumps(parsed, indent=2)[:12000]
    char_count = len(run.get("input_text") or "")
    html = TEMPLATE.render(
        run=run,
        user_email=user_email,
        tier=tier,
        char_count=char_count,
        agent_outputs=agent_outputs,
        agent_json=agent_json,
        parsed_json_str=parsed_json_str,
    )
    return HTML(string=html).write_pdf()
