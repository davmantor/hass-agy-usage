"""Antigravity Usage integration for Home Assistant."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
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
    USAGE_API_URL,
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
        }

        try:
            session = aiohttp_client.async_get_clientsession(self.hass)

            # Step 1: loadCodeAssist to obtain the project ID
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

            # Step 2: fetchAvailableModels using the project ID
            body = {"project": project} if project else {}
            fam_resp = await session.post(
                USAGE_API_URL,
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if fam_resp.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed - token may be invalid")
            fam_resp.raise_for_status()
            raw = await fam_resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching usage data: {err}") from err

        tier_info = lca_data.get("currentTier", {})
        tier = tier_info.get("name") or tier_info.get("id")
        models = _parse_usage(raw)
        return {"models": models, "tier": tier, "reset_groups": _build_reset_groups(models)}

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


def _parse_usage(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse raw API response into flat sensor data dict."""
    data: dict[str, Any] = {}
    seen_names: set[str] = set()

    for model_id, model_info in raw.get("models", {}).items():
        # Skip internal/autocomplete-only models
        if (
            model_id.startswith(("chat_", "tab_", "rev"))
            or "image" in model_id
            or "mquery" in model_id
            or "lite" in model_id
        ):
            continue

        quota_info = model_info.get("quotaInfo")
        if not quota_info:
            continue

        remaining_fraction = quota_info.get("remainingFraction")
        if remaining_fraction is None:
            continue

        reset_time = quota_info.get("resetTime")
        seconds_until_reset = None
        if reset_time:
            try:
                reset_dt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
                seconds_until_reset = max(0, int((reset_dt - datetime.now(UTC)).total_seconds()))
            except ValueError:
                pass

        label = model_info.get("displayName") or model_info.get("label") or model_id
        if label in seen_names:
            continue
        seen_names.add(label)

        key = f"model_{model_id.replace('-', '_').replace('.', '_')}"
        data[key] = {
            "name": label,
            "value": round(remaining_fraction * 100, 1),
            "reset_time": reset_time,
            "seconds_until_reset": seconds_until_reset,
            "is_exhausted": remaining_fraction == 0,
        }

    return data


def _build_reset_groups(models: dict[str, Any]) -> list[dict[str, Any]]:
    """Group models by reset time and derive a display name per group."""
    groups: dict[str, set[str]] = {}
    for key, info in models.items():
        rt = info.get("reset_time")
        if not rt:
            continue
        if rt not in groups:
            groups[rt] = set()
        if "gemini" in key:
            groups[rt].add("Gemini")
        elif "claude" in key:
            groups[rt].add("Claude")
        elif "gpt" in key:
            groups[rt].add("GPT")

    return [
        {"name": " & ".join(sorted(families)) + " Reset", "reset_time": rt}
        for rt, families in groups.items()
        if families
    ]
