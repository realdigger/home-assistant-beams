"""Config flow for BEAMS Light."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BeamsApiError, BeamsLightApi, normalize_base_url
from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    base_url = normalize_base_url(data[CONF_HOST])
    session = async_get_clientsession(hass)
    api = BeamsLightApi(session, base_url)

    state = await api.async_get_state()
    kit = await api.async_get_kit()
    channels = await api.async_get_channels()

    configured_name = str(data.get(CONF_NAME) or "").strip()
    title = configured_name or DEFAULT_NAME
    unique_source = base_url


    try:
        info = await api.async_info()
        general = info.get("general") if isinstance(info.get("general"), dict) else {}
        if not configured_name or configured_name == DEFAULT_NAME:
            title = general.get("hostName") or title
        unique_source = general.get("deviceId") or title or base_url
    except BeamsApiError:
        pass

    kit_name = kit.get("kit_name") or kit.get("name") or "BEAMS Light"
    unique_id = f"{unique_source}-{kit_name}".lower().replace(" ", "_")

    if not isinstance(state, dict):
        raise BeamsApiError("Invalid state/get response")
    if not isinstance(channels, list):
        raise BeamsApiError("Invalid channels/get response")

    return {"title": title, "base_url": base_url, "unique_id": unique_id}


class BeamsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BEAMS Light."""

    VERSION = 12

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except BeamsApiError:
                _LOGGER.exception("Cannot connect to BEAMS Light controller")
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception while configuring BEAMS Light")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={CONF_HOST: info["base_url"], CONF_NAME: user_input.get(CONF_NAME) or info["title"]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Allow updating the controller URL without removing the integration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(info["unique_id"], raise_on_progress=False)
                self._abort_if_unique_id_mismatch()
            except BeamsApiError:
                _LOGGER.exception("Cannot connect to BEAMS Light controller")
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception while reconfiguring BEAMS Light")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    title=info["title"],
                    data_updates={
                        CONF_HOST: info["base_url"],
                        CONF_NAME: user_input.get(CONF_NAME) or info["title"],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Optional(CONF_NAME, default=entry.data.get(CONF_NAME, entry.title)): str,
                }
            ),
            errors=errors,
        )
