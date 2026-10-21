"""Config flow for Ferroli Connect with MQTT auto-discovery."""
from __future__ import annotations

import asyncio
import re

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_BRIDGE_ENABLED,
    CONF_BRIDGE_HOST,
    CONF_CLIENT_ID,
    CONF_OWNER_SLUG,
    CONF_PASSWORD,
    DEFAULT_BRIDGE_HOST,
    DOMAIN,
)

SCAN_SECONDS = 40


class FerroliConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._found: dict = {}

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Entry point: scan the broker to auto-discover the receiver."""
        self._found = await self._scan()
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            cid = user_input[CONF_CLIENT_ID].strip()
            if cid:
                await self.async_set_unique_id(cid)
                self._abort_if_unique_id_configured()
                data = {
                    CONF_CLIENT_ID: cid,
                    CONF_OWNER_SLUG: (user_input.get(CONF_OWNER_SLUG) or "").strip(),
                    CONF_PASSWORD: user_input.get(CONF_PASSWORD) or "",
                    CONF_BRIDGE_ENABLED: user_input.get(CONF_BRIDGE_ENABLED, True),
                    CONF_BRIDGE_HOST: user_input.get(CONF_BRIDGE_HOST)
                    or DEFAULT_BRIDGE_HOST,
                }
                return self.async_create_entry(
                    title=f"Ferroli {cid[:10]}", data=data
                )
            # sin client id: reintenta el escaneo del broker
            self._found = await self._scan()
            errors["base"] = "no_client_id"

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CLIENT_ID, default=self._found.get("cid") or ""
                ): str,
                vol.Optional(
                    CONF_OWNER_SLUG, default=self._found.get("owner_slug") or ""
                ): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_BRIDGE_ENABLED, default=True): bool,
                vol.Optional(CONF_BRIDGE_HOST, default=DEFAULT_BRIDGE_HOST): str,
            }
        )
        status = "found" if self._found.get("cid") else "not_found"
        return self.async_show_form(
            step_id="confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "cid": self._found.get("cid") or "-",
                "status": status,
            },
        )

    async def _scan(self, timeout: int = SCAN_SECONDS) -> dict:
        """Listen briefly to learn client id, prefix and owner slug."""
        found: dict = {"cid": None, "prefix": None, "owner_slug": None}
        done = asyncio.Event()

        @callback
        def on_msg(msg) -> None:
            parts = msg.topic.split("/")
            if len(parts) >= 4 and parts[1] in (
                "dev_realt",
                "dev2app",
                "dev2ser_req_info",
            ):
                found["prefix"] = parts[2]
                found["cid"] = parts[3]
            if (
                len(parts) >= 5
                and parts[1] == "app2dev"
                and "$of$" in parts[4]
                and "_" in parts[4]
            ):
                found["owner_slug"] = parts[4].split("_", 1)[1].split("$of$")[0]
            payload = msg.payload
            if isinstance(payload, (bytes, bytearray)) and b"owner_slug" in payload:
                match = re.search(rb'"owner_slug"\s*:\s*"([^"]+)"', payload)
                if match:
                    found["owner_slug"] = match.group(1).decode("utf-8", "ignore")
            if found["cid"]:
                done.set()

        unsubs = []
        try:
            for topic in (
                "/dev_realt/#",
                "/dev2app/#",
                "/dev2ser_req_info/#",
                "/app2dev/#",
                "/ser2dev_noti/#",
            ):
                unsubs.append(
                    await mqtt.async_subscribe(
                        self.hass, topic, on_msg, encoding=None
                    )
                )
        except Exception:  # noqa: BLE001  (mqtt not ready)
            for unsub in unsubs:
                unsub()
            return found

        try:
            await asyncio.wait_for(done.wait(), timeout)
            await asyncio.sleep(3)  # give the owner_slug a chance too
        except asyncio.TimeoutError:
            pass
        for unsub in unsubs:
            unsub()
        return found
