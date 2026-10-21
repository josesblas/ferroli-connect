"""Constants for the Ferroli Connect integration."""
from __future__ import annotations

DOMAIN = "ferroli_connect"
PLATFORMS = ["climate", "sensor"]

CONF_CLIENT_ID = "client_id"
CONF_PASSWORD = "password"
CONF_OWNER_SLUG = "owner_slug"
CONF_BRIDGE_ENABLED = "bridge_enabled"
CONF_BRIDGE_HOST = "bridge_host"
CONF_BRIDGE_PORT = "bridge_port"

DEFAULT_BRIDGE_HOST = "18.158.187.64"
DEFAULT_BRIDGE_PORT = 1883

# dispatcher signal (format with entry_id)
SIGNAL_UPDATE = "ferroli_connect_update_{}"

# device -> cloud (relayed local broker -> Topband)
OUT_TOPICS = ["/dev_realt/#", "/dev2app/#", "/dev2ser_req_info/#"]
# cloud -> device (relayed Topband -> local broker)
IN_TOPICS = ["/app2dev/#", "/ser2dev_noti/#", "/ser2dev_res/#"]
