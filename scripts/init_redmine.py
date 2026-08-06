#!/usr/bin/env python3
"""Redmine 初期化スクリプト

Redmine REST API を叩いて、以下のリソースを作成（既存ならスキップ）：
 - プロジェクト「社内問い合わせ」(internal-inquiry)
 - トラッカー「問い合わせ」
 - ステータス定義（対応待ち・対応中・対応済・クローズ待ち・クローズ）
 - ロール：営業担当者・サポート担当者
 - ロール別ワークフロー

.env ファイルに API Key / プロジェクト ID を書き出す。
"""

from __future__ import annotations

import json
import os
import sys
import time
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

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

# Redmine のステータス名 → ポータルが利用する英語キー。
# Redmine 6.1 の既定ステータスをポータル用の日本語表示へ変換する。
STATUS_KEY_ALIASES = {
    "open": {"new", "open", "新規", "対応待ち"},
    "in_progress": {"in progress", "in_progress", "progress", "進行中", "対応中"},
    "answered": {"resolved", "回答済", "対応済"},
    "pending_close": {"rejected", "クローズ待ち"},
    "closed": {"closed", "終了", "クローズ"},
}

ROLES_TO_CREATE = [
    {"name": "営業担当者", "description": "営業担当。チケットの作成・確認・クローズ"},
    {"name": "サポート担当者", "description": "サポート/技術担当。回答・ステータス更新"},
]


# ── HTTP Helpers ───────────────────────────────────────────────────

def _login(client: httpx.Client) -> str:
    """Redmine に Basic 認証し、現在のユーザーの API Key を取得する。"""
    r = client.get(
        "/users/current.json",
        auth=(ADMIN_USER, ADMIN_PASS),
        headers={"Accept": "application/json"},
    )
    if r.status_code in (401, 403):
        print("  ✗ Login failed: invalid admin credentials or password change required")
        sys.exit(1)
    if r.status_code == 404:
        print("  ✗ Login failed: Redmine REST API is disabled or unavailable")
        print("    Enable 'REST web service' in Redmine Administration > Settings > API")
        sys.exit(1)
    if r.status_code != 200:
        print(f"  ✗ Login failed (status={r.status_code})")
        sys.exit(1)

    try:
        api_key = r.json()["user"]["api_key"]
    except (KeyError, TypeError, ValueError):
        print("  ✗ Login succeeded, but Redmine did not return the user's API key")
        print("    Confirm that REST API access is enabled for this Redmine instance")
        sys.exit(1)
    return api_key


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

def _trust_environment_proxy(url: str) -> bool:
    """Use environment proxies except for an explicitly local Redmine URL."""
    hostname = urlparse(url).hostname
    if not hostname:
        return True
    if hostname.casefold() == "localhost":
        return False
    try:
        return not ip_address(hostname).is_loopback
    except ValueError:
        return True


def wait_for_redmine(timeout_sec: int = 180):
    print(f"  → Waiting for Redmine at {REDMINE_URL} ...")
    client = httpx.Client(
        base_url=REDMINE_URL,
        timeout=10.0,
        follow_redirects=True,
        trust_env=_trust_environment_proxy(REDMINE_URL),
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
    """Rails bootstrap で作成されたトラッカーの存在を確認する。"""
    trackers = _get(client, "trackers", api_key)
    for t in trackers.get("trackers", []):
        if t["name"] == TRACKER_NAME:
            print(f"  ✓ Tracker '{TRACKER_NAME}' (ID={t['id']}) already exists")
            return t["id"]

    print(f"  ✗ Tracker '{TRACKER_NAME}' does not exist")
    print("    Run the redmine-init service to provision administration resources")
    sys.exit(1)


def check_statuses(client: httpx.Client, api_key: str) -> Dict[str, int]:
    """ステータス一覧を表示し、英語キー→ID のマッピングを返す。"""
    statuses = _get(client, "issue_statuses", api_key)
    status_list = statuses.get("issue_statuses", [])

    mapping: Dict[str, int] = {}
    print("  Current issue statuses:")
    for s in status_list:
        name = s["name"]
        sid = s["id"]
        normalized_names = {
            name.strip().casefold(),
            str(s.get("slug", "")).strip().casefold(),
        }
        key = next(
            (
                candidate
                for candidate, aliases in STATUS_KEY_ALIASES.items()
                if normalized_names & aliases
            ),
            None,
        )
        if key:
            mapping[key] = sid
            print(f"    ID={sid} '{name}' → {key}")
        else:
            print(f"    ID={sid} '{name}' (unknown — ignored)")

    required_keys = {
        "open",
        "in_progress",
        "answered",
        "pending_close",
        "closed",
    }
    if not required_keys.issubset(mapping.keys()):
        missing = required_keys - mapping.keys()
        print(f"  ✗ Missing status keys: {missing}")
        print(f"    Redmine デフォルトステータスが変更されている可能性があります")
        sys.exit(1)

    return mapping


def ensure_roles(client: httpx.Client, api_key: str):
    """Rails bootstrap で作成されたカスタムロールの存在を確認する。"""
    roles = _get(client, "roles", api_key)
    existing_names = {r["name"] for r in roles.get("roles", [])}

    missing = [rc["name"] for rc in ROLES_TO_CREATE if rc["name"] not in existing_names]
    if missing:
        print(f"  ✗ Missing roles: {', '.join(missing)}")
        print("    Run the redmine-init service to provision administration resources")
        sys.exit(1)
    for rc in ROLES_TO_CREATE:
        print(f"  ✓ Role '{rc['name']}' already exists")


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
    print("  ✓ Login succeeded and API key was obtained")

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
