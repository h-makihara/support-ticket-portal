#!/usr/bin/env python3
"""Redmine 初期化スクリプト

Redmine REST API を叩いて、以下のリソースを作成（既存ならスキップ）：
 - プロジェクト「社内問い合わせ」(internal-inquiry)
 - トラッカー「問い合わせ」
 - ステータス定義（デフォルトの 4 つをそのまま利用）
 - ロール：営業担当者・サポート担当者

.env ファイルに API Key / プロジェクト ID を書き出す。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ── 設定 ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

REDMINE_URL = os.getenv("REDMINE_URL", "http://localhost:3000")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")

PROJECT_IDENTIFIER = "internal-inquiry"
PROJECT_NAME = "社内問い合わせ"
TRACKER_NAME = "問い合わせ"

# Redmine デフォルトステータスのスロット名 → 英語キー (backend が利用)
# Redmine 6.1 default: New(1), In Progress(2), Reopened(3), Closed(4)
DEFAULT_STATUS_KEYS = {
    "New":        "open",
    "In Progress":"in_progress",
    "Reopened":   "feedback",
    "Closed":     "closed",
}

ROLES_TO_CREATE = [
    {"name": "営業担当者", "description": "営業担当。チケットの作成・確認・クローズ"},
    {"name": "サポート担当者", "description": "サポート/技術担当。回答・ステータス更新"},
]


# ── HTTP Helpers ───────────────────────────────────────────────────

def _login(client: httpx.Client) -> str:
    """admin でログインし API Key を取得"""
    r = client.get("/my/account/key.json", auth=(ADMIN_USER, ADMIN_PASS))
    if r.status_code != 200:
        print(f"  ✗ Login failed (status={r.status_code}): {r.text[:300]}")
        sys.exit(1)
    return r.json()["api_key"]


def _get(client: httpx.Client, path: str, api_key: str, params: Optional[Dict] = None):
    hdrs = {"X-Redmine-API-Key": api_key}
    r = client.get(f"/{path}.json", headers=hdrs, params=params or {})
    if r.status_code != 200:
        print(f"  ✗ GET {path} failed (status={r.status_code}): {r.text[:300]}")
        sys.exit(1)
    return r.json()


def _post(client: httpx.Client, path: str, api_key: str, data: Dict):
    hdrs = {"X-Redmine-API-Key": api_key}
    r = client.post(f"/{path}.json", headers=hdrs, json=data)
    if r.status_code not in (201, 204):
        print(f"  ✗ POST {path} failed (status={r.status_code}): {r.text[:300]}")
        sys.exit(1)
    return r.json()


# ── Redmine wait ───────────────────────────────────────────────────

def wait_for_redmine(timeout_sec: int = 180):
    print(f"  → Waiting for Redmine at {REDMINE_URL} ...")
    client = httpx.Client(
        base_url=REDMINE_URL, timeout=10.0, follow_redirects=True
    )
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            r = client.get("/login")
            if r.status_code in (200, 302):
                print(f"  ✓ Redmine is up!")
                return client
        except Exception as e:
            # print(f"    retry... ({e})")
            pass
        time.sleep(3)

    print(f"  ✗ Timed out waiting for Redmine after {timeout_sec}s")
    sys.exit(1)


# ── Setup Functions ────────────────────────────────────────────────

def ensure_project(client: httpx.Client, api_key: str) -> int:
    """プロジェクトがなければ作成。存在する場合は ID を返す。"""
    projects = _get(client, "projects", api_key, {"limit": 100})
    for p in projects.get("projects", []):
        if p["identifier"] == PROJECT_IDENTIFIER:
            print(f"  ✓ Project '{PROJECT_NAME}' (ID={p['id']}) already exists")
            return p["id"]

    payload = {"project": {
        "name": PROJECT_NAME,
        "identifier": PROJECT_IDENTIFIER,
        "description": "営業からの問い合わせを Redmine で管理するプロジェクト",
    }}
    result = _post(client, "projects", api_key, payload)
    pid = result["project"]["id"]
    print(f"  ✓ Created project '{PROJECT_NAME}' (ID={pid})")
    return pid


def ensure_tracker(client: httpx.Client, api_key: str) -> int:
    """トラッカーがなければ作成。"""
    trackers = _get(client, "trackers", api_key)
    for t in trackers.get("trackers", []):
        if t["name"] == TRACKER_NAME:
            print(f"  ✓ Tracker '{TRACKER_NAME}' (ID={t['id']}) already exists")
            return t["id"]

    payload = {"tracker": {"name": TRACKER_NAME}}
    result = _post(client, "trackers", api_key, payload)
    tid = result["tracker"]["id"]
    print(f"  ✓ Created tracker '{TRACKER_NAME}' (ID={tid})")
    return tid


def check_statuses(client: httpx.Client, api_key: str) -> Dict[str, int]:
    """ステータス一覧を表示し、英語キー→ID のマッピングを返す。"""
    statuses = _get(client, "issue_statuses", api_key)
    status_list = statuses.get("issue_statuses", [])

    mapping: Dict[str, int] = {}
    print("  Current issue statuses:")
    for s in status_list:
        name = s["name"]
        sid = s["id"]
        key = DEFAULT_STATUS_KEYS.get(name)
        if key:
            mapping[key] = sid
            print(f"    ID={sid} '{name}' → {key}")
        else:
            print(f"    ID={sid} '{name}' (unknown — ignored)")

    required_keys = {"open", "in_progress", "feedback", "closed"}
    if not required_keys.issubset(mapping.keys()):
        missing = required_keys - mapping.keys()
        print(f"  ✗ Missing status keys: {missing}")
        print(f"    Redmine デフォルトステータスが変更されている可能性があります")
        sys.exit(1)

    return mapping


def ensure_roles(client: httpx.Client, api_key: str):
    """カスタムロールがなければ作成。"""
    roles = _get(client, "roles", api_key)
    existing_names = {r["name"] for r in roles.get("roles", [])}

    for rc in ROLES_TO_CREATE:
        name = rc["name"]
        if name in existing_names:
            print(f"  ✓ Role '{name}' already exists")
            continue

        payload = {"role": {
            "name": name,
            "description": rc["description"],
        }}
        _post(client, "roles", api_key, payload)
        print(f"  ✓ Created role '{name}'")


# ── .env generation ────────────────────────────────────────────────

def write_env(api_key: str, project_id: int, tracker_id: int, status_map: Dict[str, int]):
    """プロジェクトルートの .env を生成"""
    env_path = ROOT_DIR / ".env"
    lines = [
        "# ── Redmine ───────────────────────",
        f'REDMINE_BASE_URL="{REDMINE_URL}"',
        f'REDMINE_API_KEY="{api_key}"',
        f'REDMINE_PROJECT_ID="{project_id}"',
        f'REDMINE_TRACKER_ID="{tracker_id}"',
        "",
        "# ── Generated status mapping (for reference) ─",
    ]
    for key, sid in sorted(status_map.items()):
        lines.append(f"#   {key} -> status_id={sid}")
    lines.append("")

    env_path.write_text("\n".join(lines))
    print(f"  ✓ Written .env to {env_path}")


# ── Main ───────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  Redmine Ticket Portal — 初期化スクリプト")
    print("=" * 50)

    # 1. Wait for Redmine
    print("\n[Step 1] Waiting for Redmine ...")
    client = wait_for_redmine()

    # 2. Login & get API key
    print("[Step 2] Logging in as admin ...")
    api_key = _login(client)
    print(f"  ✓ API Key: {api_key[:8]}...{api_key[-8:]}")

    # 3. Project
    print("[Step 3] Ensuring project ...")
    project_id = ensure_project(client, api_key)

    # 4. Tracker
    print("[Step 4] Ensuring tracker ...")
    tracker_id = ensure_tracker(client, api_key)

    # 5. Statuses check
    print("[Step 5] Checking statuses ...")
    status_map = check_statuses(client, api_key)

    # 6. Roles
    print("[Step 6] Ensuring roles ...")
    ensure_roles(client, api_key)

    # 7. Write .env
    print("\n[Done] Generating .env ...")
    write_env(api_key, project_id, tracker_id, status_map)

    client.close()

    print("\n" + "=" * 50)
    print("  ✅ 初期化完了！")
    print("=" * 50)
    print(f"\n Redmine   : {REDMINE_URL}")
    print(f" Project   : {PROJECT_NAME} (ID={project_id})")
    print(f" Tracker   : {TRACKER_NAME} (ID={tracker_id})")
    print(f" Statuses  : {status_map}")
    print()


if __name__ == "__main__":
    main()
