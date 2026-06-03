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
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    OAUTH_CLIENT_ID,
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
        }

        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            resp = await session.post(
                USAGE_API_URL, headers=headers, json={}, timeout=aiohttp.ClientTimeout(total=15)
            )
            if resp.status == 401:
                raise ConfigEntryAuthFailed("Authentication failed - token may be invalid")
            resp.raise_for_status()
            raw = await resp.json()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching usage data: {err}") from err

        return _parse_usage(raw)

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

    cascade_data = raw.get("cascadeModelConfigData", {})
    client_configs = cascade_data.get("clientModelConfigs", [])
    
    for model in client_configs:
        model_id = model.get("modelOrAlias", {}).get("model", "unknown")
        label = model.get("label", model.get("displayName", model_id))
        quota_info = model.get("quotaInfo", {})
        remaining_fraction = quota_info.get("remainingFraction")
        
        if remaining_fraction is not None:
            percent = round(remaining_fraction * 100, 1)
            key = f"model_{model_id.replace('-', '_').replace('.', '_')}"
            
            data[key] = {
                "name": label,
                "value": percent,
                "reset_time": quota_info.get("resetTime")
            }

    return data
