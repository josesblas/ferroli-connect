"""Ferroli Connect (Topband) binary MQTT protocol: decode and encode.

The receiver speaks a TLV payload (tag 2B + length 2B + value) after a fixed
22-byte header. This module is pure Python with no Home Assistant deps so it
can be unit-tested standalone.
"""
from __future__ import annotations

import time

HEADER = 22

# thermostat tags (0x10xx)
THERMO = {0x1000: "room_temp", 0x1010: "setpoint", 0x100F: "mode"}
# boiler tags (0x20xx)
BOILER = {
    0x2000: "dhw_temp",        # agua caliente sanitaria
    0x2002: "flow_temp",       # ida / caldera
    0x2003: "boiler_setpoint",
    0x2023: "dhw_flow",        # caudal ACS
}
# tags that are value x10 (one decimal)
DIV10 = {
    "room_temp", "setpoint", "dhw_temp", "flow_temp",
    "boiler_setpoint", "dhw_flow",
}
MODE_MAP = {1: "manual", 4: "schedule"}


def parse_tlv(data: bytes, start: int = HEADER) -> dict[int, bytes]:
    out: dict[int, bytes] = {}
    i = start
    while i + 4 <= len(data):
        tag = (data[i] << 8) | data[i + 1]
        length = (data[i + 2] << 8) | data[i + 3]
        i += 4
        if i + length > len(data):
            break
        out[tag] = data[i:i + length]
        i += length
    return out


def boiler_state(value: int) -> str:
    """Map the OpenTherm status bitmap (tag 0x2014) to a readable state."""
    if value == 0:
        return "off"
    if value & 4:
        return "dhw"
    if value & 2:
        return "heating"
    return "on"


def decode(payload: bytes) -> dict:
    """Decode a device payload into a flat dict of known values."""
    if payload[:1] == b"{":
        return {}
    tlv = parse_tlv(payload)
    vals: dict = {}
    if 0x0017 in tlv:
        vals["_thermo_id"] = tlv[0x0017].hex()
    if 0x2024 in tlv:
        vals["_boiler_id"] = tlv[0x2024].hex()
    for tag, raw in tlv.items():
        value = int.from_bytes(raw, "big")
        if tag == 0x2014:
            vals["boiler_state"] = boiler_state(value)
            continue
        if tag == 0x100F:
            vals["mode"] = MODE_MAP.get(value, f"mode_{value}")
            continue
        key = THERMO.get(tag) or BOILER.get(tag)
        if not key:
            continue
        vals[key] = round(value / 10.0, 1) if key in DIV10 else value
    return vals


def build_set_setpoint(celsius: float, thermo_id: str, seq: int | None = None) -> bytes:
    """Build an /app2dev command that sets the thermostat setpoint (manual mode).

    Mirrors exactly what the official app sends: manual mode (100f=1) + setpoint
    (1010 = celsius*10) + thermostat id (0017).
    """
    if seq is None:
        seq = int(time.time()) & 0xFF
    centi = int(round(celsius * 10))
    ts2 = int(time.time() * 1000).to_bytes(8, "big")
    frame = bytes([0x00, 0x02, 0x13, seq, 0x64]) + (0).to_bytes(8, "big") + ts2 + bytes([0x0D])
    frame += bytes([0x10, 0x0F, 0x00, 0x01, 0x01])
    frame += bytes([0x10, 0x10, 0x00, 0x02]) + centi.to_bytes(2, "big")
    frame += bytes([0x00, 0x17, 0x00, 0x04]) + bytes.fromhex(thermo_id)
    return frame


def command_topic(prefix: str, cid: str, owner_slug: str) -> str:
    """Topic the app publishes commands to (device subscribes with wildcard)."""
    slug = owner_slug or "ha"
    return f"/app2dev/{prefix}/{cid}/{int(time.time())}_{slug}$of$HA"


# "Poll all" query frames captured from the official app when it opens: they ask
# the device to report every tag (values sent as zero). The 4-byte device id is
# substituted at runtime. Replaying them makes the receiver report its full state
# immediately instead of waiting for its sparse periodic frames.
_POLL_BOILER = "00011300000000000000000000000001a153ce02420d202400045555aaaa001800010020000002000020010002000020020002000020030002000020040001002005000400000000200700010020080001002009000100200a000100200b00020000200c00020000200d000100200e0001002010000100201100010020120001002013000100201400010020150001002016000100201700010020180001002019000100201a000100201b000100201c000100201e000100201f000100202000010020210001002022000100202300010020240004000000002026000200002027000200002028000200002030000100"
_POLL_THERMO = "00011301640000000000000000000001a153ce82bc0d001700040696e07f000000040000000000030004000000000004000800000000000000000005000100000600010000130001000018000100100000020000100100020000100200020000100300020000100400020000100500020000100600020000100700010010080001001009000100100a000100100b000100100c000100100d000100100e000100100f000100101000020000101100010010120001001013000100101400010010160001001017000200001018000100101b0009000000000000000000101d001a0000000000000000000000000000000000000000000000000000101e001a0000000000000000000000000000000000000000000000000000101f001a00000000000000000000000000000000000000000000000000001020001a00000000000000000000000000000000000000000000000000001021001a00000000000000000000000000000000000000000000000000001022001a00000000000000000000000000000000000000000000000000001023001a00000000000000000000000000000000000000000000000000001024000200001025000200001039000200002004000100200c000200002030000100"


def _build_poll(template_hex: str, old_id: str, new_id: str) -> bytes:
    data = bytearray.fromhex(template_hex.replace(old_id, new_id, 1))
    data[13:21] = int(time.time() * 1000).to_bytes(8, "big")  # refresh timestamp
    return bytes(data)


def build_poll_boiler(boiler_id: str) -> bytes:
    return _build_poll(_POLL_BOILER, "5555aaaa", boiler_id)


def build_poll_thermo(thermo_id: str) -> bytes:
    return _build_poll(_POLL_THERMO, "0696e07f", thermo_id)
