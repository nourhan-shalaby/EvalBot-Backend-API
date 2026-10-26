"""Shared infrastructure for the EvalBot platform: settings, database, auth, file storage."""
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, Header, HTTPException

logger = logging.getLogger("evalbot.platform")

# --------------------------------------------------------------------------------------
# Settings (all from environment / Space secrets)
# --------------------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "evalbot")
DEV_AUTH = os.getenv("EVALBOT_DEV_AUTH", "") == "1"          # local testing only: accepts "dev:<uuid>:<email>"
LOCAL_STORAGE_DIR = os.getenv("EVALBOT_LOCAL_STORAGE", "./platform_storage")


def enabled() -> bool:
    return bool(DATABASE_URL)


def public_config() -> Dict[str, Any]:
    return {"enabled": enabled(), "supabase_url": SUPABASE_URL, "supabase_anon_key": SUPABASE_ANON_KEY,
            "dev_auth": DEV_AUTH}


# --------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------
_pool = None
_pool_lock = threading.Lock()


def pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool

                _pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=True,
                                       kwargs={"row_factory": dict_row, "autocommit": True,
                                               "prepare_threshold": None})  # pgbouncer-compatible
    return _pool


def init_db() -> None:
    if not enabled():
        logger.warning("DATABASE_URL not set: platform features are disabled")
        return
    sql = open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf-8").read()
    with pool().connection() as conn:
        conn.execute(sql)
    logger.info("Database schema ready")


def _adapt(params):
    from psycopg.types.json import Jsonb

    if params is None:
        return None
    if isinstance(params, dict):
        return {k: Jsonb(v) if isinstance(v, (dict, list)) else v for k, v in params.items()}
    return [Jsonb(v) if isinstance(v, (dict, list)) else v for v in params]


def q(sql: str, params=None) -> List[Dict]:
    with pool().connection() as conn:
        cur = conn.execute(sql, _adapt(params))
        return cur.fetchall() if cur.description else []


def q1(sql: str, params=None) -> Optional[Dict]:
    rows = q(sql, params)
    return rows[0] if rows else None


# --------------------------------------------------------------------------------------
# Auth (Supabase access tokens)
# --------------------------------------------------------------------------------------
_token_cache: Dict[str, tuple] = {}


def _verify_token(token: str) -> Dict:
    hit = _token_cache.get(token)
    if hit and hit[1] > time.time():
        return hit[0]
    if DEV_AUTH and token.startswith("dev:"):
        _, uid, email = token.split(":", 2)
        user = {"id": uid, "email": email}
    else:
        if not SUPABASE_URL:
            raise HTTPException(500, "Authentication is not configured")
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/user", timeout=10,
                      headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY})
        if r.status_code != 200:
            raise HTTPException(401, "Your session has expired. Please sign in again.")
        d = r.json()
        user = {"id": d["id"], "email": d.get("email"),
                "name": (d.get("user_metadata") or {}).get("full_name") or (d.get("user_metadata") or {}).get("name")}
    _token_cache[token] = (user, time.time() + 300)
    return user


def current_user(authorization: str = Header(default="")) -> Dict:
    if not enabled():
        raise HTTPException(503, "The platform is not configured yet")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in")
    user = _verify_token(authorization.split(" ", 1)[1].strip())
    prof = q1("select * from profiles where id = %s", [user["id"]])
    if prof is None:
        prof = q1("insert into profiles (id, email, full_name) values (%s, %s, %s) "
                  "on conflict (id) do update set email = excluded.email returning *",
                  [user["id"], user.get("email"), user.get("name")])
    return prof


def recruiter(user: Dict = Depends(current_user)) -> Dict:
    if user["role"] != "recruiter" or not user.get("company_id"):
        raise HTTPException(403, "This page is for company accounts")
    return user


# --------------------------------------------------------------------------------------
# File storage (Supabase Storage, or a local folder for development)
# --------------------------------------------------------------------------------------
def _storage_headers(content_type: Optional[str] = None) -> Dict[str, str]:
    h = {"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}", "apikey": SUPABASE_SERVICE_ROLE_KEY}
    if content_type:
        h["Content-Type"] = content_type
    return h


def _use_supabase_storage() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


# Optional: keep recordings and PDFs in a private Hugging Face dataset (100 GB+ free) instead of
# Supabase Storage (1 GB free). Enabled when HF_STORAGE_REPO and HF_TOKEN are both set.
HF_STORAGE_REPO = os.getenv("HF_STORAGE_REPO", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")
_hf_cache_dir = os.path.join(LOCAL_STORAGE_DIR, ".hf_cache")


def _use_hf_storage() -> bool:
    return bool(HF_STORAGE_REPO and HF_TOKEN)


def storage_backend() -> str:
    return "huggingface" if _use_hf_storage() else "supabase" if _use_supabase_storage() else "local"


def _hf_api():
    from huggingface_hub import HfApi
    return HfApi(token=HF_TOKEN)


def ensure_bucket() -> None:
    if _use_hf_storage():
        _hf_api().create_repo(HF_STORAGE_REPO, repo_type="dataset", private=True, exist_ok=True)
        os.makedirs(_hf_cache_dir, exist_ok=True)
        logger.info("File storage: private HF dataset %s", HF_STORAGE_REPO)
        return
    if not _use_supabase_storage():
        os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
        return
    r = httpx.get(f"{SUPABASE_URL}/storage/v1/bucket/{STORAGE_BUCKET}", headers=_storage_headers(), timeout=15)
    if r.status_code != 200:
        r = httpx.post(f"{SUPABASE_URL}/storage/v1/bucket", headers=_storage_headers("application/json"),
                       json={"id": STORAGE_BUCKET, "name": STORAGE_BUCKET, "public": False}, timeout=15)
        logger.info("Created storage bucket %s: %s", STORAGE_BUCKET, r.status_code)


def put_file(path: str, data: bytes, content_type: str) -> str:
    if _use_hf_storage():
        _hf_api().upload_file(path_or_fileobj=data, path_in_repo=path, repo_id=HF_STORAGE_REPO,
                              repo_type="dataset", commit_message=f"add {path}")
        full = os.path.join(_hf_cache_dir, path)  # keep a local copy so reads are instant
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        return path
    if not _use_supabase_storage():
        full = os.path.join(LOCAL_STORAGE_DIR, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        return path
    r = httpx.post(f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{path}", content=data, timeout=120,
                   headers={**_storage_headers(content_type), "x-upsert": "true"})
    if r.status_code >= 300:
        raise RuntimeError(f"Storage upload failed: {r.status_code} {r.text[:200]}")
    return path


def get_file(path: str) -> bytes:
    if _use_hf_storage():
        full = os.path.join(_hf_cache_dir, path)
        if not os.path.exists(full):
            from huggingface_hub import hf_hub_download
            try:
                return open(hf_hub_download(HF_STORAGE_REPO, path, repo_type="dataset", token=HF_TOKEN,
                                            local_dir=_hf_cache_dir), "rb").read()
            except Exception as e:
                raise RuntimeError(f"Storage download failed: {e}")
        with open(full, "rb") as f:
            return f.read()
    if not _use_supabase_storage():
        with open(os.path.join(LOCAL_STORAGE_DIR, path), "rb") as f:
            return f.read()
    r = httpx.get(f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{path}", headers=_storage_headers(), timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Storage download failed: {r.status_code}")
    return r.content


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
