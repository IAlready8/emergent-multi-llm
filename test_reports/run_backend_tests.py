#!/usr/bin/env python3
"""Prometheus backend smoke tests."""
import json, time, uuid, sys, io
import requests

BASE = "https://multi-agent-hub-64.preview.emergentagent.com/api"
results = {"passed": [], "failed": []}

def rec(name, ok, evidence=""):
    (results["passed"] if ok else results["failed"]).append({"name": name, "evidence": evidence})
    print(f"{'PASS' if ok else 'FAIL'}: {name} :: {evidence[:200]}")

# 1) health
r = requests.get(f"{BASE}/health", timeout=10)
rec("GET /health", r.status_code == 200 and r.json().get("status") == "ok", str(r.status_code))
# security headers
h = r.headers
rec("Security headers", h.get("x-content-type-options") == "nosniff" and "x-frame-options" in {k.lower() for k in h.keys()}, f"XCTO={h.get('x-content-type-options')} XFO={h.get('x-frame-options')}")

# 2) Admin login
r = requests.post(f"{BASE}/auth/login", json={"email":"admin@prometheus.ai","password":"AdminPass123!"}, timeout=10)
admin_ok = r.status_code == 200 and "access_token" in r.json()
rec("Admin login", admin_ok, f"{r.status_code} {r.text[:150]}")
if not admin_ok:
    print("Cannot continue without admin"); 
    with open("/tmp/results.json","w") as f: json.dump(results,f)
    sys.exit(0)
admin_token = r.json()["access_token"]
AH = {"Authorization": f"Bearer {admin_token}"}

r = requests.get(f"{BASE}/auth/me", headers=AH, timeout=10)
me = r.json() if r.status_code == 200 else {}
rec("GET /auth/me admin", r.status_code == 200 and me.get("is_admin") and me.get("subscription",{}).get("tier")=="enterprise", f"{r.status_code} is_admin={me.get('is_admin')} tier={me.get('subscription',{}).get('tier')}")

# 3) Fresh user signup
email = f"user_{uuid.uuid4().hex[:8]}@test.com"
r = requests.post(f"{BASE}/auth/signup", json={"email":email,"password":"TestPass123!","name":"Test User"}, timeout=10)
signup_ok = r.status_code in (200,201) and "access_token" in r.json()
rec("Signup free user", signup_ok, f"{r.status_code} {r.text[:120]}")
free_token = r.json().get("access_token") if signup_ok else None
FH = {"Authorization": f"Bearer {free_token}"} if free_token else {}

# 4) Templates
r = requests.get(f"{BASE}/templates", headers=AH, timeout=10)
tpl_list = r.json() if r.status_code == 200 else []
if isinstance(tpl_list, dict): tpl_list = tpl_list.get("templates", tpl_list.get("items", []))
rec("GET /templates (>=3)", isinstance(tpl_list,list) and len(tpl_list)>=3, f"{r.status_code} count={len(tpl_list) if isinstance(tpl_list,list) else 'na'}")

# 5) Billing tiers
r = requests.get(f"{BASE}/billing/tiers", timeout=10)
rec("GET /billing/tiers", r.status_code == 200, f"{r.status_code}")

# 6) Stripe checkout - all keys
for key in ["pro_monthly","pro_annual","enterprise_monthly","enterprise_annual"]:
    r = requests.post(f"{BASE}/billing/checkout", headers=AH, json={"lookup_key":key,"origin_url":"https://example.com"}, timeout=15)
    url = r.json().get("checkout_url","") if r.status_code==200 else ""
    rec(f"Checkout {key}", r.status_code==200 and url.startswith("https://checkout.stripe.com"), f"{r.status_code} url={url[:60]}")

# 7) Create run - paste
r = requests.post(f"{BASE}/runs", headers=AH, json={"input_text":"The quick brown fox jumps over the lazy dog. This is a test document about AI.","input_type":"paste","template_id":"doc_insight"}, timeout=20)
run_ok = r.status_code in (200,201) and "run_id" in (r.json() if r.status_code<300 else {})
rec("POST /runs paste (admin)", run_ok, f"{r.status_code} {r.text[:150]}")
run_id = r.json().get("run_id") if run_ok else None

# 8) SSE streaming
sse_events = {"snapshot":0, "agent_status":0, "agent_token":0, "run_status":0}
if run_id:
    try:
        with requests.get(f"{BASE}/runs/{run_id}/stream", params={"token":admin_token}, stream=True, timeout=45) as sr:
            ct = sr.headers.get("content-type","")
            rec("SSE content-type", "text/event-stream" in ct, ct)
            start = time.time()
            cur_event = None
            for line in sr.iter_lines(decode_unicode=True):
                if line is None: continue
                if line.startswith("event:"):
                    cur_event = line.split(":",1)[1].strip()
                    if cur_event in sse_events: sse_events[cur_event]+=1
                    if cur_event == "run_status":
                        # peek data
                        pass
                if time.time()-start > 40: break
                if sse_events["run_status"]>=1 and sse_events["agent_token"]>=1: 
                    # give a bit more
                    if time.time()-start > 5: break
    except Exception as e:
        rec("SSE stream", False, str(e))
    rec("SSE events (snapshot,agent_status,agent_token)", sse_events["snapshot"]>=1 and sse_events["agent_status"]>=1 and sse_events["agent_token"]>=1, str(sse_events))

# 9) Wait for run completion
if run_id:
    final = None
    for _ in range(30):
        r = requests.get(f"{BASE}/runs/{run_id}", headers=AH, timeout=10)
        if r.status_code == 200:
            final = r.json()
            if final.get("status") in ("completed","failed","error"): break
        time.sleep(2)
    ok = final and final.get("status")=="completed" and len(final.get("agent_outputs",{}) or {})>=3
    rec("Run completed with 3 agent_outputs", ok, f"status={final.get('status') if final else 'None'} agents={list((final or {}).get('agent_outputs',{}).keys())}")

# 10) URL fetch valid + SSRF block
r = requests.post(f"{BASE}/runs", headers=AH, json={"input_type":"url","url":"https://example.com","template_id":"doc_insight"}, timeout=20)
rec("POST /runs url=example.com", r.status_code in (200,201), f"{r.status_code} {r.text[:120]}")

r = requests.post(f"{BASE}/runs", headers=AH, json={"input_type":"url","url":"http://127.0.0.1","template_id":"doc_insight"}, timeout=10)
rec("SSRF block private IP", r.status_code in (400,403), f"{r.status_code} {r.text[:100]}")

# 11) Upload
files = {"file": ("test.txt", io.BytesIO(b"hello world test content"), "text/plain")}
r = requests.post(f"{BASE}/uploads", headers=AH, files=files, timeout=15)
up_ok = r.status_code in (200,201) and "file_id" in (r.json() if r.status_code<300 else {})
rec("POST /uploads txt", up_ok, f"{r.status_code} {r.text[:120]}")
if up_ok:
    fid = r.json()["file_id"]
    r = requests.post(f"{BASE}/runs", headers=AH, json={"input_type":"file","file_ids":[fid],"template_id":"doc_insight"}, timeout=20)
    rec("POST /runs file", r.status_code in (200,201), f"{r.status_code} {r.text[:120]}")

# 12) Workflows - admin allowed, free forbidden
r = requests.post(f"{BASE}/workflows", headers=AH, json={"name":"test-wf","agents":[{"type":"Analyzer","provider":"gemini"}]}, timeout=10)
rec("Admin create workflow", r.status_code in (200,201), f"{r.status_code} {r.text[:120]}")
if free_token:
    r = requests.post(f"{BASE}/workflows", headers=FH, json={"name":"test-wf-free","agents":[{"type":"Analyzer","provider":"gemini"}]}, timeout=10)
    rec("Free workflow 403", r.status_code == 403, f"{r.status_code}")

# 13) Free tier restrictions
if free_token:
    r = requests.post(f"{BASE}/runs", headers=FH, json={"input_text":"hi","input_type":"paste","template_id":"doc_insight","agents":[{"type":"AnomalyDetector","provider":"gemini"}]}, timeout=10)
    rec("Free AnomalyDetector 403", r.status_code in (400,403), f"{r.status_code} {r.text[:100]}")
    r = requests.post(f"{BASE}/runs", headers=FH, json={"input_text":"hi","input_type":"paste","template_id":"doc_insight","agents":[{"type":"Synthesizer","provider":"gemini"}]}, timeout=10)
    rec("Free Synthesizer 403", r.status_code in (400,403), f"{r.status_code} {r.text[:100]}")

# 14) Feedback
r = requests.post(f"{BASE}/feedback", headers=AH, json={"message":"test"}, timeout=10)
rec("POST /feedback", r.status_code in (200,201), f"{r.status_code}")

# 15) Admin overview + metrics
r = requests.get(f"{BASE}/admin/overview", headers=AH, timeout=10)
rec("GET /admin/overview", r.status_code == 200, f"{r.status_code}")
r = requests.get(f"{BASE}/admin/metrics", headers=AH, timeout=10)
rec("GET /admin/metrics prom", r.status_code == 200 and "text/plain" in r.headers.get("content-type",""), f"{r.status_code} ct={r.headers.get('content-type')}")

# 16) Export json + pdf
if run_id:
    r = requests.get(f"{BASE}/runs/{run_id}/export.json", headers=AH, timeout=15)
    rec("export.json admin", r.status_code==200 and "application/json" in r.headers.get("content-type",""), f"{r.status_code} ct={r.headers.get('content-type')}")
    r = requests.get(f"{BASE}/runs/{run_id}/export.pdf", headers=AH, timeout=30)
    rec("export.pdf admin(pro/ent)", r.status_code==200 and "application/pdf" in r.headers.get("content-type",""), f"{r.status_code} ct={r.headers.get('content-type')}")

# 17) GDPR export + delete on free user (last)
if free_token:
    r = requests.get(f"{BASE}/gdpr/export", headers=FH, timeout=10)
    rec("GDPR export", r.status_code==200, f"{r.status_code}")
    # free-tier pdf export denial - use admin's run id (free user can't access other's run; use a fresh free run? skip if not possible)
    r = requests.delete(f"{BASE}/gdpr/account", headers=FH, timeout=10)
    rec("GDPR delete account", r.status_code==200, f"{r.status_code}")

with open("/app/test_reports/raw_results.json","w") as f:
    json.dump(results,f,indent=2)
print(f"\n\nTOTAL PASS={len(results['passed'])} FAIL={len(results['failed'])}")
