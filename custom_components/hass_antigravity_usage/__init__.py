"""Antigravity Usage integration for Home Assistant."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CCPA_METADATA,
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOAD_CODE_ASSIST_URL,
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_TOKEN_URL,
    QUOTA_SUMMARY_URL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type AntigravityUsageConfigEntry = ConfigEntry[AntigravityUsageCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AntigravityUsageConfigEntry) -> bool:
    """Set up Antigravity Usage from a config entry."""
    coordinator = AntigravityUsageCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AntigravityUsageConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: AntigravityUsageConfigEntry) -> None:
    """Handle options update."""
    coordinator: AntigravityUsageCoordinator = entry.runtime_data
    interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator.update_interval = timedelta(seconds=interval)


class AntigravityUsageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch Antigravity usage data."""

    config_entry: AntigravityUsageConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AntigravityUsageConfigEntry) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch usage data from the API."""
        await self._ensure_valid_token()

        access_token = self.config_entry.data[CONF_ACCESS_TOKEN]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "antigravity",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        }

        try:
            session = aiohttp_client.async_get_clientsession(self.hass)

            # Step 1: loadCodeAssist to get project ID and current tier
            lca_resp = await session.post(
                LOAD_CODE_ASSIST_URL,
                headers=headers,
                json={"metadata": CCPA_METADATA},
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if lca_resp.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed - token may be invalid")
            lca_resp.raise_for_status()
            lca_data = await lca_resp.json()

            project = lca_data.get("cloudaicompanionProject")
            if isinstance(project, dict):
                project = project.get("id")

            # Step 2: retrieveUserQuotaSummary for grouped weekly/5h quota data
            body = {"project": project} if project else {}
            quota_resp = await session.post(
                QUOTA_SUMMARY_URL,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if quota_resp.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed - token may be invalid")
            quota_resp.raise_for_status()
            quota_data = await quota_resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching usage data: {err}") from err

        tier_info = lca_data.get("currentTier", {})
        tier = tier_info.get("name") or tier_info.get("id")
        return {"groups": _parse_quota_summary(quota_data), "tier": tier}

    async def _ensure_valid_token(self) -> None:
        """Refresh the access token if expired."""
        expires_at = self.config_entry.data.get(CONF_EXPIRES_AT, 0)
        if time.time() < expires_at - 60:
            return

        refresh_token = self.config_entry.data.get(CONF_REFRESH_TOKEN)
        if not refresh_token:
            raise UpdateFailed("No refresh token available")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
        }

        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            resp = await session.post(
                OAUTH_TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if not resp.ok:
                raise ConfigEntryAuthFailed(f"Token refresh failed ({resp.status})")
            token_data = await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Token refresh request failed: {err}") from err

        if "access_token" not in token_data:
            raise ConfigEntryAuthFailed("Token refresh response missing access_token")

        new_data = {
            **self.config_entry.data,
            CONF_ACCESS_TOKEN: token_data["access_token"],
            CONF_REFRESH_TOKEN: token_data.get("refresh_token", refresh_token),
            CONF_EXPIRES_AT: time.time() + token_data.get("expires_in", 3600),
        }
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)


_GROUP_NAMES: dict[str, str] = {
    "gemini": "Gemini Models",
    "3p": "Third-Party Models",
}


def _parse_quota_summary(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse retrieveUserQuotaSummary response into a list of group dicts."""
    groups = []
    for group in raw.get("groups", []):
        buckets = group.get("buckets", [])

        # Derive a stable key from the first bucket ID prefix (e.g. "gemini-weekly" → "gemini")
        key = "unknown"
        if buckets:
            first_id = buckets[0].get("bucketId", "")
            key = first_id.rsplit("-", 1)[0] if "-" in first_id else first_id

        name = _GROUP_NAMES.get(key, group.get("displayName", key))
        entry: dict[str, Any] = {"key": key, "name": name}

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
