"""Constants for Antigravity Usage integration."""

DOMAIN = "hass_antigravity_usage"

# OAuth
OAUTH_CLIENT_ID = "681255803995-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_REDIRECT_URI = "https://api.antigravity.google/oauth/callback"
OAUTH_SCOPES = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/cloud-platform"

# API
USAGE_API_URL = "https://api.antigravity.google/v1internal/usage"
PROFILE_API_URL = "https://api.antigravity.google/v1internal/profile"

# Defaults
DEFAULT_AUTH_FILE = "/config/.storage/oauth_creds.json"
DEFAULT_UPDATE_INTERVAL = 300  # seconds

# Config keys
CONF_AUTH_FILE = "auth_file"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ACCOUNT_NAME = "account_name"
CONF_SUBSCRIPTION_LEVEL = "subscription_level"

# Sensor definitions: (key, name, unit, icon, device_class)
SENSOR_DEFINITIONS = [
    ("session_usage_percent", "Session Usage", "%", "mdi:timer-sand", None),
    (
        "session_reset_time",
        "Session Reset Time",
        None,
        "mdi:timer-refresh",
        "timestamp",
    ),
    ("week_usage_percent", "Week Usage", "%", "mdi:calendar-week", None),
    ("week_usage_pace", "Week Usage Pace", "%", "mdi:speedometer", None),
    ("week_reset_time", "Weekly Reset Time", None, "mdi:calendar-clock", "timestamp"),
    ("extra_usage_enabled", "Extra Usage Enabled", None, "mdi:toggle-switch", None),
    ("extra_usage_percent", "Extra Usage", "%", "mdi:credit-card", None),
    (
        "extra_usage_credits",
        "Extra Usage Credits",
        "credits",
        "mdi:credit-card-outline",
        "monetary"
    ),
    (
        "extra_usage_limit",
        "Extra Usage Limit",
        "credits",
        "mdi:credit-card-settings",
        "monetary"
    ),
    ("api_error", "API Error", "errors", "mdi:alert-circle", None),
]
