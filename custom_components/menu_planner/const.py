"""Constants for the Menu Planner integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "menu_planner"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_TOKEN: Final = "token"

DEFAULT_PORT: Final = 8098
TOKEN_HEADER: Final = "X-Menu-Planner-Token"
REQUEST_TIMEOUT: Final = 10
SCAN_INTERVAL: Final = timedelta(seconds=60)


SERVICE_LOG_EATEN: Final = "log_eaten"
SERVICE_SET_STOCK: Final = "set_stock"
SERVICE_SWAP_TODAY: Final = "swap_today"

ATTR_DATE: Final = "date"
ATTR_ITEM: Final = "item"
ATTR_IN_STOCK: Final = "in_stock"
ATTR_DINNER_ID: Final = "dinner_id"

CARD_BUNDLE_URL: Final = "/menu_planner/menu-planner-cards.js"
CARD_BUNDLE_FILENAME: Final = "menu-planner-cards.js"
