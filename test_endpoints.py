"""
Test script: compare all quota/usage endpoints for Antigravity.
Reads credentials from ~/.gemini/antigravity-cli/antigravity-oauth-token,
refreshes if expired, then calls each endpoint and dumps raw responses.
"""

import asyncio
import json
import time
from pathlib import Path

import aiohttp

CRED_FILE = Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"

# From const.py
CLIENT_ID_PARTS = ["1071006060591", "-tmhssin2h21lc", "re235vtolojh4g403ep.ap", "ps.googleusercontent.com"]
CLIENT_ID = "".join(CLIENT_ID_PARTS)
SECRET_PARTS = ["GOC", "SPX-K58F", "WR486LdLJ", "1mLB8sXC", "4z6qDAf"]
CLIENT_SECRET = "".join(SECRET_PARTS)
TOKEN_URL = "https://oauth2.googleapis.com/token"

LOAD_CODE_ASSIST_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"
FETCH_MODELS_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
RETRIEVE_QUOTA_URL = "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota"
RETRIEVE_QUOTA_SUMMARY_URL = (
    "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary"
)

CCPA_METADATA = {
    "ideType": "ANTIGRAVITY",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}

BASE_HEADERS = {
    "User-Agent": "antigravity",
    "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
}


def load_creds():
    raw = json.loads(CRED_FILE.read_text())
    return raw["token"]


async def refresh_token(session: aiohttp.ClientSession, creds: dict) -> str:
    expiry_str = creds.get("expiry", "")
    # Parse expiry — strip timezone offset and compare
    try:
        from datetime import datetime, timezone
        expiry = datetime.fromisoformat(expiry_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if now < expiry:
            print(f"  Token still valid until {expiry.isoformat()}")
            return creds["access_token"]
    except Exception as e:
        print(f"  Could not parse expiry ({e}), refreshing anyway")

    print("  Token expired — refreshing...")
    resp = await session.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=aiohttp.ClientTimeout(total=15),
    )
    resp.raise_for_status()
    data = await resp.json()
    print(f"  Refreshed. Expires in {data.get('expires_in')}s")
    return data["access_token"]


async def call(session: aiohttp.ClientSession, label: str, url: str, token: str, body: dict):
    headers = {**BASE_HEADERS, "Authorization": f"Bearer {token}"}
    print(f"\n{'='*60}")
    print(f"ENDPOINT: {label}")
    print(f"URL: {url}")
    print(f"Body: {json.dumps(body, indent=2)}")
    print("-" * 60)
    try:
        resp = await session.post(url, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=15))
        print(f"Status: {resp.status}")
        if resp.status == 404:
            print("  -> 404 Not Found (endpoint may not exist)")
            return None
        raw = await resp.json(content_type=None)
        print("Response:")
        print(json.dumps(raw, indent=2))
        return raw
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return None


async def main():
    creds = load_creds()

    async with aiohttp.ClientSession() as session:
        token = await refresh_token(session, creds)

        # Step 1: loadCodeAssist — get project + tier
        lca = await call(session, "loadCodeAssist", LOAD_CODE_ASSIST_URL, token, {"metadata": CCPA_METADATA})

        project = None
        if lca:
            p = lca.get("cloudaicompanionProject")
            if isinstance(p, dict):
                project = p.get("id")
            elif isinstance(p, str):
                project = p
            print(f"\n  -> Project ID: {project}")
            tier = lca.get("currentTier", {})
            print(f"  -> Tier: {tier}")

        body_with_project = {"project": project} if project else {}

        # Step 2: fetchAvailableModels (current approach)
        await call(session, "fetchAvailableModels", FETCH_MODELS_URL, token, body_with_project)

        # Step 3: retrieveUserQuota (candidate replacement)
        await call(session, "retrieveUserQuota", RETRIEVE_QUOTA_URL, token, body_with_project)

        # Step 4: retrieveUserQuotaSummary (also mentioned in CodexBar docs)
        await call(session, "retrieveUserQuotaSummary", RETRIEVE_QUOTA_SUMMARY_URL, token, body_with_project)


_GROUP_NAMES = {"gemini": "Gemini Models", "3p": "Third-Party Models"}


def _parse_quota_summary(raw):
    """Mirror of __init__.py logic for local testing."""
    groups = []
    for group in raw.get("groups", []):
        buckets = group.get("buckets", [])
        key = "unknown"
        if buckets:
            first_id = buckets[0].get("bucketId", "")
            key = first_id.rsplit("-", 1)[0] if "-" in first_id else first_id
        name = _GROUP_NAMES.get(key, group.get("displayName", key))
        entry = {"key": key, "name": name}
        for bucket in buckets:
            window = bucket.get("window", "")
            rf = bucket.get("remainingFraction")
            rt = bucket.get("resetTime")
            if window == "weekly":
                if rf is not None:
                    entry["weekly_used"] = round((1 - rf) * 100, 1)
                if rt:
                    entry["weekly_reset_time"] = rt
            elif window == "5h":
                if rf is not None:
                    entry["session_used"] = round((1 - rf) * 100, 1)
                if rt:
                    entry["session_reset_time"] = rt
        groups.append(entry)
    return groups


async def main_with_parse():
    creds = load_creds()
    async with aiohttp.ClientSession() as session:
        token = await refresh_token(session, creds)

        lca = await call(session, "loadCodeAssist", LOAD_CODE_ASSIST_URL, token, {"metadata": CCPA_METADATA})
        project = None
        if lca:
            p = lca.get("cloudaicompanionProject")
            project = p.get("id") if isinstance(p, dict) else p

        quota_raw = await call(session, "retrieveUserQuotaSummary", RETRIEVE_QUOTA_SUMMARY_URL, token,
                               {"project": project} if project else {})

        if quota_raw:
            groups = _parse_quota_summary(quota_raw)
            print(f"\n{'='*60}")
            print("PARSED GROUPS -> SENSOR PREVIEW")
            print("="*60)
            for g in groups:
                print(f"\nGroup: {g['name']} (key={g['key']})")
                for field, label_suffix, is_ts in [
                    ("weekly_used", "Weekly Usage", False),
                    ("session_used", "Session Usage", False),
                    ("weekly_reset_time", "Weekly Reset", True),
                    ("session_reset_time", "Session Reset", True),
                ]:
                    if field in g:
                        sensor_name = f"{g['name']} {label_suffix}"
                        print(f"  [{'+' if not is_ts else 'T'}] {sensor_name:<45} = {g[field]}")

        tier_info = (lca or {}).get("currentTier", {})
        tier = tier_info.get("name") or tier_info.get("id")
        print(f"\n  [+] Subscription Tier                                     = {tier}")


if __name__ == "__main__":
    asyncio.run(main_with_parse())
