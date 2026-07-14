"""Config flow for Antigravity Usage integration."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_NAME,
    CONF_AUTH_FILE,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_SUBSCRIPTION_LEVEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AUTH_FILE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PROFILE_API_URL,
)

_LOGGER = logging.getLogger(__name__)


def _read_auth_file(path_str: str) -> dict[str, Any] | None:
    """Read and parse the auth JSON file."""
    try:
        path = Path(path_str).expanduser()
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


class AntigravityUsageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Antigravity Usage."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_file = user_input[CONF_AUTH_FILE].strip()
            auth_data = await self.hass.async_add_executor_job(_read_auth_file, auth_file)

            if auth_data is None:
                errors[CONF_AUTH_FILE] = "auth_file_unreadable"
            elif "access_token" not in auth_data or "refresh_token" not in auth_data:
                errors[CONF_AUTH_FILE] = "missing_tokens"
            else:
                # Fetch account info for display
                account_name, subscription_level = await self._fetch_account_info(
                    auth_data["access_token"]
                )

                # Build title with name and subscription level
                title_parts = ["Antigravity Usage"]
                if account_name:
                    title_parts.append(f"({account_name}")
                    if subscription_level:
                        title_parts.append(f"- {subscription_level})")
                    else:
                        title_parts[-1] += ")"
                title = " ".join(title_parts)

                await self.async_set_unique_id(auth_file)
                self._abort_if_unique_id_configured()
                
                # expiry_date is usually in ms from epoch in oauth_creds.json
                expires_at = time.time() + 3600
                if "expiry_date" in auth_data:
                    expires_at = auth_data["expiry_date"] / 1000

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_ACCESS_TOKEN: auth_data["access_token"],
                        CONF_REFRESH_TOKEN: auth_data["refresh_token"],
                        CONF_EXPIRES_AT: expires_at,
                        CONF_ACCOUNT_NAME: account_name,
                        CONF_SUBSCRIPTION_LEVEL: subscription_level,
                        CONF_AUTH_FILE: auth_file,
                    },
                    options={
                        CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_FILE, default=DEFAULT_AUTH_FILE): str,
                }
            ),
            errors=errors,
        )

    async def _fetch_account_info(self, access_token: str) -> tuple[str | None, str | None]:
        """Fetch account name and subscription level from the profile API."""
        try:
            session = aiohttp_client.async_get_clientsession(self.hass)
            resp = await session.get(
                PROFILE_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )
            if not resp.ok:
                _LOGGER.warning("Failed to fetch account profile (%s)", resp.status)
                return None, None
            profile = await resp.json()
            account = profile.get("account", {})

            # Get account name
            account_name = (
                account.get("display_name") or account.get("full_name") or account.get("email")
            )

            # Get subscription level
            subscription_level = None
            if account.get("has_antigravity_max") or account.get("has_max"):
                subscription_level = "Max"
            elif account.get("has_antigravity_pro") or account.get("has_pro"):
                subscription_level = "Pro"

            return account_name, subscription_level
        except (aiohttp.ClientError, KeyError):
            _LOGGER.exception("Error fetching account info")
            return None, None

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauth when token is invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        
        entry = self._get_reauth_entry()
        current_file = entry.data.get(CONF_AUTH_FILE, DEFAULT_AUTH_FILE)

        if user_input is not None:
            auth_file = user_input[CONF_AUTH_FILE].strip()
            auth_data = await self.hass.async_add_executor_job(_read_auth_file, auth_file)

            if auth_data is None:
                errors[CONF_AUTH_FILE] = "auth_file_unreadable"
            elif "access_token" not in auth_data or "refresh_token" not in auth_data:
                errors[CONF_AUTH_FILE] = "missing_tokens"
            else:
                account_name, subscription_level = await self._fetch_account_info(
                    auth_data["access_token"]
                )

                expires_at = time.time() + 3600
                if "expiry_date" in auth_data:
                    expires_at = auth_data["expiry_date"] / 1000

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_ACCESS_TOKEN: auth_data["access_token"],
                        CONF_REFRESH_TOKEN: auth_data["refresh_token"],
                        CONF_EXPIRES_AT: expires_at,
                        CONF_ACCOUNT_NAME: account_name,
                        CONF_SUBSCRIPTION_LEVEL: subscription_level,
                        CONF_AUTH_FILE: auth_file,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_FILE, default=current_file): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return AntigravityUsageOptionsFlow()


class AntigravityUsageOptionsFlow(OptionsFlow):
    """Handle options for Antigravity Usage."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(
                        int, vol.Range(min=60, max=3600)
                    ),
                }
            ),
        )
