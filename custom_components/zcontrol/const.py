"""Constants for the Z-Control integration."""

DOMAIN = "zcontrol"
CONF_ACCOUNT_TIME_ZONE = "account_time_zone"

# API URLs
LOGIN_URL = "https://account.zcontrolcloud.com/Account/Login"
API_BASE_URL = "https://api-v2.zcontrolcloud.com"

# Azure API Management subscription key (same for all users)
SUBSCRIPTION_KEY = "89c4308c01f8473db3565de296bad6bf"

# Polling interval in seconds
DEFAULT_SCAN_INTERVAL = 60

# Cookie name for auth token
AUTH_TOKEN_COOKIE = ".Application.AuthToken"

# Device status names
STATUS_INPUT_1 = "Input 1"
STATUS_INPUT_2 = "Input 2"
STATUS_AC_POWER = "AC Power"
STATUS_BATTERY = "Battery"

# Commands
COMMAND_ALARM_SILENCE = "ALARM_SILENCE"
COMMAND_DEVICE_RESET = "DEVICE_RESET"
