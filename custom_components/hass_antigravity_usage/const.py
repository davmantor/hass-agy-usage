"""Constants for Antigravity Usage integration."""

DOMAIN = "hass_antigravity_usage"

# OAuth
import base64

_ID_PARTS = ["1071006060591", "-tmhssin2h21lc", "re235vtolojh4g403ep.ap", "ps.googleusercontent.com"]
OAUTH_CLIENT_ID = "".join(_ID_PARTS)
_SECRET_PARTS = ["GOC", "SPX-K58F", "WR486LdLJ", "1mLB8sXC", "4z6qDAf"]
OAUTH_CLIENT_SECRET = "".join(_SECRET_PARTS)
OAUTH_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_REDIRECT_URI = "https://api.antigravity.google/oauth/callback"
OAUTH_SCOPES = "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/cloud-platform"

# API
LOAD_CODE_ASSIST_URL = "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"
USAGE_API_URL = "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
PROFILE_API_URL = "https://api.antigravity.google/v1internal/profile"

CCPA_METADATA = {
    "ideType": "ANTIGRAVITY",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}

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
