"""Prometheus — Multi-Agent Orchestration Platform backend."""
from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import io
import json
import logging
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import bcrypt
import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: F401
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from agents import RunBus, orchestrate_run  # noqa: E402
from config import AGENT_TYPES, LOOKUP_KEY_TO_TIER, TEMPLATES, TIERS, TIER_TO_LOOKUP_KEYS  # noqa: E402
from deps import (  # noqa: E402
    admin_user,
    create_access_token,
    create_refresh_token,
    current_user,
    db,
    decode_token,
    new_id,
    now_utc,
    optional_user,
    rate_limit,
)
from emails import password_reset_html, send_email  # noqa: E402
from pdf_gen import generate_pdf  # noqa: E402

logger = logging.getLogger("prometheus")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

app = FastAPI(title="Prometheus")
api = APIRouter(prefix="/api")


# =====================  Security headers middleware  =====================
class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeaders)


# =====================  Auth models  =====================
class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class ResetRequestBody(BaseModel):
    email: EmailStr


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


def _hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


async def _ensure_subscription(user_id: str) -> dict:
    sub = await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})
    if sub:
        return sub
    sub = {
        "user_id": user_id,
        "tier": "free",
        "status": "active",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "current_period_end": None,
        "runs_used": 0,
        "period_started_at": now_utc().isoformat(),
        "manual_credits": 0,
        "pending_tier": None,
        "billing_status": "current",
    }
    await db.subscriptions.insert_one(sub)
    return sub


def _serialize_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "is_admin": bool(user.get("is_admin")),
        "picture": user.get("picture"),
        "provider": user.get("provider", "password"),
    }


@api.post("/auth/signup")
async def signup(body: SignupBody):
    existing = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email already registered")
    user_id = new_id("user")
    doc = {
        "user_id": user_id,
        "email": body.email.lower(),
        "name": body.name,
        "password_hash": _hash_password(body.password),
        "provider": "password",
        "is_admin": False,
        "created_at": now_utc().isoformat(),
    }
    await db.users.insert_one(doc)
    await _ensure_subscription(user_id)
    access = create_access_token(user_id)
    refresh = create_refresh_token(user_id)
    return {"access_token": access, "refresh_token": refresh, "user": _serialize_user(doc)}


@api.post("/auth/login")
async def login(body: LoginBody, request: Request):
    rate_limit(f"login:{request.client.host}", limit=20, window_sec=300)
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if not user or not user.get("password_hash") or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if user.get("disabled"):
        raise HTTPException(403, "Account disabled")
    await _ensure_subscription(user["user_id"])
    access = create_access_token(user["user_id"])
    refresh = create_refresh_token(user["user_id"])
    return {"access_token": access, "refresh_token": refresh, "user": _serialize_user(user)}


@api.post("/auth/refresh")
async def refresh(body: RefreshBody):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid refresh token")
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    user_id = payload["sub"]
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return {"access_token": create_access_token(user_id), "refresh_token": create_refresh_token(user_id)}


@api.get("/auth/me")
async def auth_me(user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    return {"user": _serialize_user(user), "subscription": sub, "tier_config": TIERS[sub["tier"]]}


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.post("/auth/password-reset/request")
async def reset_request(body: ResetRequestBody, request: Request):
    rate_limit(f"reset:{request.client.host}", limit=5, window_sec=3600)
    user = await db.users.find_one({"email": body.email.lower()}, {"_id": 0})
    if user:
        token = new_id("rst")
        await db.password_resets.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "expires_at": (now_utc() + timedelta(hours=1)).isoformat(),
            "used": False,
        })
        origin = request.headers.get("origin") or request.headers.get("referer", "").rstrip("/")
        link = f"{origin}/reset-password?token={token}"
        await send_email(user["email"], "Reset your Prometheus password", password_reset_html(link))
    return {"ok": True}


@api.post("/auth/password-reset/confirm")
async def reset_confirm(body: ResetConfirmBody):
    rec = await db.password_resets.find_one({"token": body.token}, {"_id": 0})
    if not rec or rec.get("used"):
        raise HTTPException(400, "Invalid or used token")
    exp = datetime.fromisoformat(rec["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc():
        raise HTTPException(400, "Token expired")
    await db.users.update_one({"user_id": rec["user_id"]}, {"$set": {"password_hash": _hash_password(body.new_password)}})
    await db.password_resets.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"ok": True}


# =====================  Google Auth (Emergent)  =====================
class GoogleSessionBody(BaseModel):
    session_id: str


@api.post("/auth/google/session")
async def google_session(body: GoogleSessionBody, response: Response):
    try:
        req = urllib.request.Request(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
    except Exception as e:
        logger.error("google session error: %s", e)
        raise HTTPException(400, "Google session exchange failed")

    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = new_id("user")
        user = {
            "user_id": user_id,
            "email": email,
            "name": data.get("name") or email.split("@")[0],
            "picture": data.get("picture"),
            "provider": "google",
            "is_admin": False,
            "created_at": now_utc().isoformat(),
        }
        await db.users.insert_one(user)
    else:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"picture": data.get("picture"), "name": data.get("name") or user.get("name")}})

    await _ensure_subscription(user["user_id"])
    session_token = data["session_token"]
    expires_at = now_utc() + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": now_utc().isoformat(),
    })
    response.set_cookie("session_token", session_token, httponly=True, secure=True, samesite="none", path="/", max_age=7 * 86400)
    return {"user": _serialize_user(user)}


# =====================  Quota helpers  =====================
async def _check_quota(user_id: str) -> tuple[dict, dict]:
    sub = await _ensure_subscription(user_id)
    tier_cfg = TIERS[sub["tier"]]
    if sub.get("billing_status") == "past_due_blocked":
        raise HTTPException(402, "Payment required. Please update billing.")
    limit = tier_cfg["runs_per_period"]
    used = sub.get("runs_used", 0)
    credits = sub.get("manual_credits", 0)
    if limit is not None and used >= (limit + credits):
        raise HTTPException(402, "Run quota exceeded for this billing period")
    rate_limit(f"runs:{user_id}", tier_cfg["rate_limit_runs_per_hour"], 3600)
    return sub, tier_cfg


# =====================  Runs  =====================
class NewRunBody(BaseModel):
    input_text: str = Field(default="", max_length=2_000_000)
    input_type: str = Field(default="paste")  # paste | url | csv | file | template
    template_id: Optional[str] = None
    workflow_id: Optional[str] = None
    agents: Optional[list[dict]] = None  # [{type, provider}]
    url: Optional[str] = None
    provider: Optional[str] = None  # per-run for Pro
    file_ids: Optional[list[str]] = None


def _private_ip(hostname: str) -> bool:
    try:
        import socket
        addrinfos = socket.getaddrinfo(hostname, None)
        for info in addrinfos:
            ip = ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return True
    except Exception:
        return True
    return False


async def _fetch_url(url: str, max_bytes: int = 25 * 1024 * 1024) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Only http/https URLs allowed")
    if not parsed.hostname or _private_ip(parsed.hostname):
        raise HTTPException(400, "Blocked URL host")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Prometheus/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(max_bytes + 1)
            if len(data) > max_bytes:
                data = data[:max_bytes]
            text = data.decode("utf-8", errors="replace")
            # Strip HTML tags crudely
            text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:200_000]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"URL fetch failed: {type(e).__name__}")


def _build_agents(body: NewRunBody, tier: str) -> list[dict]:
    tier_cfg = TIERS[tier]
    allowed_types = set(tier_cfg["agents"])
    provider_mode = tier_cfg["provider_mode"]

    if body.template_id:
        tpl = next((t for t in TEMPLATES if t["id"] == body.template_id), None)
        if not tpl:
            raise HTTPException(400, "Unknown template")
        agents_src = tpl["agents"]
    elif body.agents:
        if not tier_cfg["custom_workflows"]:
            raise HTTPException(403, "Custom workflows require Pro or Enterprise")
        agents_src = body.agents
    else:
        # Default pipeline: use allowed agents
        agents_src = [{"type": t, "provider": "gemini"} for t in ["Analyzer", "Classifier", "Synthesizer"] if t in allowed_types]

    resolved: list[dict] = []
    for a in agents_src:
        atype = a.get("type")
        if atype not in AGENT_TYPES:
            raise HTTPException(400, f"Unknown agent type: {atype}")
        if atype not in allowed_types:
            raise HTTPException(403, f"Agent {atype} not available in {tier} tier")
        # Resolve provider based on tier's provider_mode
        if provider_mode == "gemini_only":
            provider = "gemini"
        elif provider_mode == "per_run":
            provider = body.provider or "gemini"
            if provider not in ("openai", "gemini"):
                provider = "gemini"
        else:  # per_agent
            provider = a.get("provider") or "gemini"
            if provider not in ("openai", "gemini"):
                provider = "gemini"
        resolved.append({
            "agent_id": new_id("ag"),
            "type": atype,
            "provider": provider,
            "status": "pending",
        })
    if not resolved:
        raise HTTPException(400, "No agents resolved")
    return resolved


@api.post("/runs")
async def create_run(body: NewRunBody, user: dict = Depends(current_user)):
    sub, tier_cfg = await _check_quota(user["user_id"])
    tier_name = sub["tier"]

    # Resolve input text
    text = body.input_text or ""
    url_list: list[str] = []
    file_names: list[str] = []

    if body.input_type == "url":
        if not body.url:
            raise HTTPException(400, "URL required")
        text = await _fetch_url(body.url)
        url_list = [body.url]
    elif body.input_type in ("csv", "file") and body.file_ids:
        for fid in body.file_ids:
            f = await db.uploads.find_one({"file_id": fid, "user_id": user["user_id"]}, {"_id": 0})
            if not f:
                continue
            file_names.append(f["filename"])
            text = (text + "\n\n" + f["content"])[:2_000_000]

    if not text.strip():
        raise HTTPException(400, "Empty input")

    agents = _build_agents(body, tier_name)

    run_id = new_id("run")
    run_doc = {
        "run_id": run_id,
        "user_id": user["user_id"],
        "workflow_id": body.workflow_id,
        "template_id": body.template_id,
        "input_type": body.input_type,
        "input_text": text,
        "file_names": file_names,
        "url_list": url_list,
        "input_hash": hashlib.sha256(text.encode()).hexdigest()[:32],
        "agents": agents,
        "status": "queued",
        "tier_at_run_time": tier_name,
        "created_at": now_utc().isoformat(),
        "started_at": None,
        "ended_at": None,
        "final_output": "",
        "agent_outputs": {},
    }
    await db.runs.insert_one(run_doc)
    run_doc.pop("_id", None)
    for a in agents:
        trace = {
            "agent_id": a["agent_id"], "run_id": run_id, "type": a["type"],
            "provider": a["provider"], "status": "pending",
        }
        await db.agent_traces.insert_one(trace)

    # Increment quota (charge on start)
    await db.subscriptions.update_one({"user_id": user["user_id"]}, {"$inc": {"runs_used": 1}})

    # Kick off orchestrator
    asyncio.create_task(orchestrate_run(run_id))

    run_doc.pop("input_text", None)
    return {"run_id": run_id, "run": run_doc}


@api.get("/runs")
async def list_runs(user: dict = Depends(current_user), limit: int = 50, status: Optional[str] = None):
    sub = await _ensure_subscription(user["user_id"])
    days = TIERS[sub["tier"]].get("history_days")
    q: dict = {"user_id": user["user_id"]}
    if status:
        q["status"] = status
    if days is not None:
        cutoff = (now_utc() - timedelta(days=days)).isoformat()
        q["created_at"] = {"$gte": cutoff}
    docs = await db.runs.find(q, {"_id": 0, "input_text": 0, "agent_outputs": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"runs": docs}


@api.get("/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(current_user)):
    run = await db.runs.find_one({"run_id": run_id, "user_id": user["user_id"]}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@api.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, token: Optional[str] = None, user: Optional[dict] = Depends(optional_user)):
    # EventSource cannot set Authorization header — accept ?token= as fallback
    resolved_user = user
    if not resolved_user and token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                resolved_user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
        except Exception:
            pass
    if not resolved_user:
        raise HTTPException(401, "Not authenticated")
    run = await db.runs.find_one({"run_id": run_id, "user_id": resolved_user["user_id"]}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")

    bus = RunBus.get(run_id)
    q = bus.subscribe()

    async def event_gen():
        try:
            # send initial snapshot
            yield f"data: {json.dumps({'event': 'snapshot', 'run': {k: run.get(k) for k in ('status','agents','final_output')}})}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(ev)}\n\n"
                if ev.get("event") == "end":
                    break
                if ev.get("event") == "run_status" and ev.get("status") in ("completed", "failed"):
                    yield f"data: {json.dumps({'event': 'end'})}\n\n"
                    break
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api.get("/runs/{run_id}/export.json")
async def export_run_json(run_id: str, user: dict = Depends(current_user)):
    run = await db.runs.find_one({"run_id": run_id, "user_id": user["user_id"]}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    return JSONResponse(run, headers={"Content-Disposition": f'attachment; filename="run_{run_id}.json"'})


@api.get("/runs/{run_id}/export.pdf")
async def export_run_pdf(run_id: str, user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    if not TIERS[sub["tier"]]["export_pdf"]:
        raise HTTPException(403, "PDF export requires Pro or Enterprise")
    run = await db.runs.find_one({"run_id": run_id, "user_id": user["user_id"]}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run["status"] not in ("completed", "completed_with_warnings", "failed"):
        raise HTTPException(400, "Run not yet complete")
    try:
        pdf_bytes = await asyncio.to_thread(generate_pdf, run, user["email"], sub["tier"])
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {type(e).__name__}")
    if len(pdf_bytes) > 25 * 1024 * 1024:
        raise HTTPException(400, "PDF too large; use JSON export")
    return Response(pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="run_{run_id}.pdf"'})


@api.delete("/runs/{run_id}")
async def delete_run(run_id: str, user: dict = Depends(current_user)):
    result = await db.runs.delete_one({"run_id": run_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Run not found")
    await db.agent_traces.delete_many({"run_id": run_id})
    return {"ok": True}


# =====================  Uploads  =====================
@api.post("/uploads")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    tier_cfg = TIERS[sub["tier"]]
    max_bytes = tier_cfg["upload_max_mb"] * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"File exceeds {tier_cfg['upload_max_mb']}MB limit")

    filename = file.filename or "upload.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"csv", "txt", "md", "json"}
    if ext not in allowed:
        raise HTTPException(400, f"File type .{ext} not allowed. Allowed: {sorted(allowed)}")

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "File must be UTF-8 text")

    if ext == "csv":
        row_count = text.count("\n") + 1
        if row_count > tier_cfg["csv_row_limit"]:
            raise HTTPException(400, f"CSV exceeds {tier_cfg['csv_row_limit']} row limit")

    file_id = new_id("file")
    await db.uploads.insert_one({
        "file_id": file_id, "user_id": user["user_id"], "filename": filename,
        "ext": ext, "size": len(content), "content": text,
        "created_at": now_utc().isoformat(),
    })
    return {"file_id": file_id, "filename": filename, "size": len(content), "ext": ext}


# =====================  Templates & Workflows  =====================
@api.get("/templates")
async def list_templates():
    return {"templates": TEMPLATES}


class WorkflowBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = ""
    agents: list[dict]


@api.get("/workflows")
async def list_workflows(user: dict = Depends(current_user)):
    docs = await db.workflows.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"workflows": docs}


@api.post("/workflows")
async def create_workflow(body: WorkflowBody, user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    tier_cfg = TIERS[sub["tier"]]
    if not tier_cfg["custom_workflows"]:
        raise HTTPException(403, "Custom workflows require Pro or Enterprise")
    count = await db.workflows.count_documents({"user_id": user["user_id"]})
    lim = tier_cfg["workflow_storage_limit"]
    if lim is not None and count >= lim:
        raise HTTPException(403, f"Workflow storage limit ({lim}) reached")
    allowed_types = set(tier_cfg["agents"])
    for a in body.agents:
        if a.get("type") not in allowed_types:
            raise HTTPException(403, f"Agent {a.get('type')} not allowed in {sub['tier']}")
    wf = {
        "workflow_id": new_id("wf"),
        "user_id": user["user_id"],
        "name": body.name,
        "description": body.description,
        "agents": body.agents,
        "created_at": now_utc().isoformat(),
    }
    await db.workflows.insert_one(wf)
    return wf


@api.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, user: dict = Depends(current_user)):
    r = await db.workflows.delete_one({"workflow_id": workflow_id, "user_id": user["user_id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Workflow not found")
    return {"ok": True}


# =====================  Billing  =====================
class CheckoutBody(BaseModel):
    lookup_key: str  # pro_monthly | pro_annual | enterprise_monthly | enterprise_annual
    origin_url: str


@api.post("/billing/checkout")
async def billing_checkout(body: CheckoutBody, user: dict = Depends(current_user)):
    if body.lookup_key not in LOOKUP_KEY_TO_TIER:
        raise HTTPException(400, "Invalid lookup_key")
    prices = stripe.Price.list(lookup_keys=[body.lookup_key], active=True, limit=1).data
    if not prices:
        raise HTTPException(500, "Price not found in Stripe")
    price = prices[0]

    sub = await _ensure_subscription(user["user_id"])
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        cust = stripe.Customer.create(email=user["email"], name=user.get("name"), metadata={"user_id": user["user_id"]})
        customer_id = cust.id
        await db.subscriptions.update_one({"user_id": user["user_id"]}, {"$set": {"stripe_customer_id": customer_id}})

    kwargs = dict(
        customer=customer_id,
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription",
        success_url=f"{body.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{body.origin_url}/billing",
        metadata={"user_id": user["user_id"], "lookup_key": body.lookup_key},
        subscription_data={"metadata": {"user_id": user["user_id"], "lookup_key": body.lookup_key}},
    )
    try:
        session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
    except stripe.error.InvalidRequestError as e:
        msg = (e.user_message or "").lower()
        if "managed payments" in msg or "ineligible" in msg:
            session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
        else:
            raise HTTPException(400, e.user_message or "checkout failed")

    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["user_id"], "lookup_key": body.lookup_key,
        "amount": (price.unit_amount or 0), "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
    })
    return {"checkout_url": session.url, "session_id": session.id}


@api.get("/billing/status/{session_id}")
async def billing_status(session_id: str):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await db.payment_transactions.update_one(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": s.subscription,
                              "updated_at": now_utc().isoformat()}},
                )
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
                # Update subscription tier
                if record.get("user_id") and record.get("lookup_key"):
                    tier, _ = LOOKUP_KEY_TO_TIER.get(record["lookup_key"], ("free", "month"))
                    await db.subscriptions.update_one(
                        {"user_id": record["user_id"]},
                        {"$set": {"tier": tier, "status": "active", "stripe_subscription_id": s.subscription,
                                  "runs_used": 0, "period_started_at": now_utc().isoformat(), "billing_status": "current"}},
                    )
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"], "payment_status": record["payment_status"]}


@api.post("/billing/portal")
async def billing_portal(user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    if not sub.get("stripe_customer_id"):
        raise HTTPException(400, "No billing account yet")
    return_url = os.environ.get("STRIPE_BILLING_PORTAL_RETURN_URL") or "https://example.com/billing"
    portal = stripe.billing_portal.Session.create(customer=sub["stripe_customer_id"], return_url=return_url)
    return {"url": portal.url}


@api.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]

    if t == "checkout.session.completed":
        session_id = obj["id"]
        await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "stripe_subscription_id": obj.get("subscription"), "updated_at": now_utc().isoformat()}},
        )
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id")
        lookup_key = meta.get("lookup_key")
        if user_id and lookup_key and lookup_key in LOOKUP_KEY_TO_TIER:
            tier, _ = LOOKUP_KEY_TO_TIER[lookup_key]
            await db.subscriptions.update_one(
                {"user_id": user_id},
                {"$set": {"tier": tier, "status": "active", "stripe_subscription_id": obj.get("subscription"),
                          "runs_used": 0, "period_started_at": now_utc().isoformat(), "billing_status": "current"}},
            )
    elif t in ("customer.subscription.updated", "customer.subscription.created"):
        sub_id = obj["id"]
        cust_id = obj.get("customer")
        status = obj.get("status")
        items = obj.get("items", {}).get("data", [])
        lookup_key = None
        if items:
            lookup_key = items[0].get("price", {}).get("lookup_key")
        update = {"stripe_subscription_id": sub_id, "status": status}
        if lookup_key and lookup_key in LOOKUP_KEY_TO_TIER:
            update["tier"], _ = LOOKUP_KEY_TO_TIER[lookup_key]
        if status == "past_due":
            update["billing_status"] = "past_due_grace"
        elif status == "active":
            update["billing_status"] = "current"
        await db.subscriptions.update_one({"stripe_customer_id": cust_id}, {"$set": update})
    elif t == "customer.subscription.deleted":
        cust_id = obj.get("customer")
        await db.subscriptions.update_one({"stripe_customer_id": cust_id}, {"$set": {"tier": "free", "status": "canceled"}})
    elif t == "invoice.payment_failed":
        cust_id = obj.get("customer")
        await db.subscriptions.update_one({"stripe_customer_id": cust_id}, {"$set": {"billing_status": "past_due_grace"}})
    elif t == "invoice.paid":
        cust_id = obj.get("customer")
        await db.subscriptions.update_one({"stripe_customer_id": cust_id}, {"$set": {"billing_status": "current", "runs_used": 0, "period_started_at": now_utc().isoformat()}})
    return {"status": "ok"}


@api.get("/billing/tiers")
async def get_tiers():
    return {"tiers": TIERS}


# =====================  Feedback & GDPR  =====================
class FeedbackBody(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)


@api.post("/feedback")
async def submit_feedback(body: FeedbackBody, user: dict = Depends(current_user)):
    doc = {"feedback_id": new_id("fb"), "user_id": user["user_id"], "email": user["email"],
           "message": body.message, "rating": body.rating, "created_at": now_utc().isoformat()}
    await db.feedback.insert_one(doc)
    return {"ok": True}


@api.get("/gdpr/export")
async def gdpr_export(user: dict = Depends(current_user)):
    sub = await _ensure_subscription(user["user_id"])
    if sub["tier"] == "free":
        rate_limit(f"gdpr_export:{user['user_id']}", 1, 86400)
    profile = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    runs = await db.runs.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(10000)
    workflows = await db.workflows.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    fbs = await db.feedback.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    export = {"profile": profile, "subscription": sub, "runs": runs, "workflows": workflows, "feedback": fbs, "exported_at": now_utc().isoformat()}
    return JSONResponse(export, headers={"Content-Disposition": 'attachment; filename="prometheus_export.json"'})


@api.delete("/gdpr/account")
async def gdpr_delete(user: dict = Depends(current_user)):
    uid = user["user_id"]
    await db.runs.delete_many({"user_id": uid})
    await db.agent_traces.delete_many({"run_id": {"$regex": "."}})  # coarse cleanup by run relation
    await db.workflows.delete_many({"user_id": uid})
    await db.uploads.delete_many({"user_id": uid})
    await db.feedback.delete_many({"user_id": uid})
    await db.subscriptions.delete_many({"user_id": uid})
    await db.user_sessions.delete_many({"user_id": uid})
    await db.password_resets.delete_many({"user_id": uid})
    await db.users.delete_one({"user_id": uid})
    await db.deletion_receipts.insert_one({"user_id": uid, "email": user["email"], "deleted_at": now_utc().isoformat()})
    return {"ok": True, "deleted_at": now_utc().isoformat()}


# =====================  Admin  =====================
@api.get("/admin/overview")
async def admin_overview(admin: dict = Depends(admin_user)):
    users_count = await db.users.count_documents({})
    runs_total = await db.runs.count_documents({})
    runs_failed = await db.runs.count_documents({"status": "failed"})
    subs = await db.subscriptions.find({}, {"_id": 0}).to_list(10000)
    revenue_month = 0
    tier_counts = {"free": 0, "pro": 0, "enterprise": 0}
    for s in subs:
        tier_counts[s.get("tier", "free")] = tier_counts.get(s.get("tier", "free"), 0) + 1
        if s.get("tier") == "pro" and s.get("status") == "active":
            revenue_month += 29
        elif s.get("tier") == "enterprise" and s.get("status") == "active":
            revenue_month += 199
    recent_users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(20).to_list(20)
    recent_runs = await db.runs.find({}, {"_id": 0, "input_text": 0, "agent_outputs": 0}).sort("created_at", -1).limit(20).to_list(20)
    fb = await db.feedback.find({}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
    return {
        "users": users_count, "runs": runs_total, "runs_failed": runs_failed,
        "revenue_month_estimate_usd": revenue_month, "tier_counts": tier_counts,
        "recent_users": recent_users, "recent_runs": recent_runs, "recent_feedback": fb,
    }


@api.get("/admin/metrics")
async def admin_metrics(admin: dict = Depends(admin_user)):
    users_count = await db.users.count_documents({})
    runs_total = await db.runs.count_documents({})
    runs_completed = await db.runs.count_documents({"status": "completed"})
    runs_failed = await db.runs.count_documents({"status": "failed"})
    lines = [
        f'prometheus_users_total {users_count}',
        f'prometheus_runs_total {runs_total}',
        f'prometheus_runs_completed {runs_completed}',
        f'prometheus_runs_failed {runs_failed}',
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@api.get("/health")
async def health():
    return {"status": "ok", "ts": now_utc().isoformat()}


# =====================  Bootstrap: admin user  =====================
@app.on_event("startup")
async def bootstrap_admin():
    admin_email = "admin@prometheus.ai"
    admin_pw = "AdminPass123!"
    existing = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if not existing:
        uid = new_id("user")
        await db.users.insert_one({
            "user_id": uid, "email": admin_email, "name": "Admin",
            "password_hash": _hash_password(admin_pw), "provider": "password",
            "is_admin": True, "created_at": now_utc().isoformat(),
        })
        await _ensure_subscription(uid)
        # Grant enterprise tier
        await db.subscriptions.update_one({"user_id": uid}, {"$set": {"tier": "enterprise"}})
        logger.info("seeded admin user: %s / %s", admin_email, admin_pw)


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    from deps import client as mongo_client
    mongo_client.close()
