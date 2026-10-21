"""Ferroli Connect integration.

Reads the receiver's MQTT traffic from the local broker, decodes the binary
protocol into native entities, optionally bridges the device to the Topband
cloud (so the official app keeps working), and controls the setpoint.
"""
from __future__ import annotations

import logging

import paho.mqtt.client as paho

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from . import protocol
from .const import (
    CONF_BRIDGE_ENABLED,
    CONF_BRIDGE_HOST,
    CONF_BRIDGE_PORT,
    CONF_CLIENT_ID,
    CONF_OWNER_SLUG,
    CONF_PASSWORD,
    DEFAULT_BRIDGE_HOST,
    DEFAULT_BRIDGE_PORT,
    DOMAIN,
    IN_TOPICS,
    OUT_TOPICS,
    PLATFORMS,
    SIGNAL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


class FerroliRuntime:
    """Owns the MQTT subscriptions, the Topband bridge and the device state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.cid: str = entry.data[CONF_CLIENT_ID]
        self.prefix: str = self.cid[:10]
        self.password: str = entry.data[CONF_PASSWORD]
        self.owner_slug: str = entry.data.get(CONF_OWNER_SLUG) or ""
        self.bridge_enabled: bool = entry.data.get(CONF_BRIDGE_ENABLED, True)
        self.bridge_host: str = entry.data.get(CONF_BRIDGE_HOST, DEFAULT_BRIDGE_HOST)
        self.bridge_port: int = entry.data.get(CONF_BRIDGE_PORT, DEFAULT_BRIDGE_PORT)
        self.state: dict = {}
        self.thermo_id: str | None = None
        self.boiler_id: str | None = None
        self._polled_boiler = False
        self._polled_thermo = False
        self._tb: paho.Client | None = None
        self._unsubs: list = []
        self._rx = 0
        self._store: Store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")

    def _save_data(self) -> dict:
        return {
            "state": self.state,
            "thermo_id": self.thermo_id,
            "boiler_id": self.boiler_id,
            "owner_slug": self.owner_slug,
        }

    async def async_start(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.state = stored.get("state") or {}
            self.thermo_id = stored.get("thermo_id")
            self.boiler_id = stored.get("boiler_id")
            if stored.get("owner_slug") and not self.owner_slug:
                self.owner_slug = stored["owner_slug"]
            _LOGGER.info("Ferroli estado recuperado: %d valores", len(self.state))
        # consigna placeholder (0 = nunca arranca la caldera) hasta que llegue
        # el valor real o el usuario la fije; mantiene la rueda siempre usable.
        self.state.setdefault("setpoint", 0)
        for topic in OUT_TOPICS:
            unsub = await mqtt.async_subscribe(
                self.hass, topic, self._on_local, encoding=None
            )
            self._unsubs.append(unsub)
        # aprender owner_slug (necesario para el control) del trafico app/nube
        for topic in ("/app2dev/#", "/ser2dev_noti/#"):
            unsub = await mqtt.async_subscribe(
                self.hass, topic, self._on_meta, encoding=None
            )
            self._unsubs.append(unsub)
        if self.bridge_enabled:
            await self.hass.async_add_executor_job(self._start_bridge)

    @callback
    def _on_meta(self, msg) -> None:
        if self.owner_slug:
            return
        if "$of$HA" in msg.topic:
            return  # ignora nuestros propios comandos / polls
        parts = msg.topic.split("/")
        slug = None
        if len(parts) >= 5 and parts[1] == "app2dev" and "$of$" in parts[4] and "_" in parts[4]:
            slug = parts[4].split("_", 1)[1].split("$of$")[0]
        elif isinstance(msg.payload, (bytes, bytearray)) and b"owner_slug" in msg.payload:
            import re

            match = re.search(rb'"owner_slug"\s*:\s*"([^"]+)"', msg.payload)
            if match:
                slug = match.group(1).decode("utf-8", "ignore")
        if slug and slug != "ha":
            self.owner_slug = slug
            _LOGGER.info("Ferroli owner_slug aprendido automaticamente")
            self._store.async_delay_save(self._save_data, 10)

    @callback
    def _on_local(self, msg) -> None:
        self._rx += 1
        if self._rx <= 5:
            payload_len = len(msg.payload) if msg.payload else 0
            _LOGGER.info(
                "Ferroli RX #%d %s (%d bytes, type %s)",
                self._rx, msg.topic, payload_len, type(msg.payload).__name__,
            )
        payload: bytes = msg.payload
        if isinstance(payload, str):
            payload = payload.encode("latin-1", "ignore")
        if self._tb is not None:
            self._tb.publish(msg.topic, payload, qos=0)
        vals = protocol.decode(payload)
        if not vals:
            return
        if vals.get("_thermo_id"):
            self.thermo_id = vals["_thermo_id"]
        if vals.get("_boiler_id"):
            self.boiler_id = vals["_boiler_id"]
        changed = False
        for key, value in vals.items():
            if not key.startswith("_"):
                self.state[key] = value
                changed = True
        if changed:
            self._store.async_delay_save(self._save_data, 10)
            async_dispatcher_send(
                self.hass, SIGNAL_UPDATE.format(self.entry.entry_id)
            )
        if not self._polled_boiler and self.boiler_id:
            self._polled_boiler = True
            self.hass.async_create_task(self._poll_boiler())
        if not self._polled_thermo and self.thermo_id:
            self._polled_thermo = True
            self.hass.async_create_task(self._poll_thermo())

    def _start_bridge(self) -> None:
        client = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id=self.cid)
        client.username_pw_set(self.cid, self.password)
        client.on_connect = self._tb_on_connect
        client.on_message = self._tb_on_message
        try:
            client.connect(self.bridge_host, self.bridge_port, 30)
        except OSError as err:
            _LOGGER.warning("Topband bridge connect failed: %s", err)
            return
        client.loop_start()
        self._tb = client
        _LOGGER.info("Topband bridge started (clientid %s)", self.cid)

    def _tb_on_connect(self, client, userdata, flags, rc, props=None) -> None:
        for topic in IN_TOPICS:
            client.subscribe(topic)

    def _tb_on_message(self, client, userdata, msg) -> None:
        # relay cloud -> device onto the local broker (thread-safe)
        self.hass.add_job(mqtt.async_publish, self.hass, msg.topic, msg.payload)

    async def async_set_setpoint(self, celsius: float) -> None:
        if not self.thermo_id:
            _LOGGER.warning("Aun sin id del termostato; ignoro la consigna")
            return
        # el receptor no valida el owner_slug: con un placeholder vale,
        # asi el control funciona tambien sin la app oficial (100% local).
        frame = protocol.build_set_setpoint(celsius, self.thermo_id)
        topic = protocol.command_topic(self.prefix, self.cid, self.owner_slug)
        await mqtt.async_publish(self.hass, topic, frame)
        self.state["setpoint"] = round(celsius, 1)
        self._store.async_delay_save(self._save_data, 10)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    async def _publish_poll(self, frame: bytes) -> None:
        import asyncio

        await asyncio.sleep(1)
        topic = protocol.command_topic(self.prefix, self.cid, self.owner_slug)
        await mqtt.async_publish(self.hass, topic, frame)

    async def _poll_boiler(self) -> None:
        try:
            await self._publish_poll(protocol.build_poll_boiler(self.boiler_id))
            _LOGGER.info("Ferroli: poll de caldera enviado")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Poll caldera fallido: %s", err)

    async def _poll_thermo(self) -> None:
        try:
            await self._publish_poll(protocol.build_poll_thermo(self.thermo_id))
            _LOGGER.info("Ferroli: poll de termostato enviado")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Poll termostato fallido: %s", err)

    async def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._tb is not None:
            tb = self._tb
            self._tb = None
            await self.hass.async_add_executor_job(tb.loop_stop)
            tb.disconnect()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ferroli Connect from a config entry."""
    runtime = FerroliRuntime(hass, entry)
    await runtime.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime: FerroliRuntime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.async_stop()
    return unloaded
