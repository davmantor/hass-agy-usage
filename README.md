# Antigravity Usage - Home Assistant Integration

A custom Home Assistant integration that monitors your Google Antigravity baseline quotas (session, week) and AI Credit overages/spending.

## Sensors

- **Session Usage** - Current 5-hour session utilization (%)
- **Session Reset Time** - When the session limit resets
- **Week Usage** - Current 7-day utilization (%)
- **Week Usage Pace** - Comparison against elapsed time (%)
- **Weekly Reset Time** - When the weekly limit resets
- **Extra Usage Enabled** - Whether extra usage (AI Credit overages) is enabled
- **Extra Usage** - Extra usage utilization (%)
- **Extra Usage Credits** - Credits consumed this month ($)
- **Extra Usage Limit** - Monthly credit limit ($)
- **API Error** - 1 if polling failed, 0 if successful

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS.
2. Restart Home Assistant.
3. Install "Antigravity Usage".
4. Go to Settings → Devices & Services → Add Integration → "Antigravity Usage".
5. Follow the instructions.

### Manual

1. Copy `custom_components/hass_antigravity_usage/` to your HA `custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via the UI.

## Setup

The integration uses Google OAuth flow:

1. When adding the integration, you'll be shown an authorization URL.
2. Open the URL in your browser and log in to your Google account.
3. After authorizing, copy the returned code and paste it into the Home Assistant config flow.

## Options

- **Update interval** - How often to poll the usage API (default: 300 seconds, min: 60, max: 3600).

## Dashboard

A pre-built dashboard is included in the `dashboards/` directory. To use it:

1. Go to Settings → Dashboards → Add Dashboard
2. Click the three-dot menu → "Edit Dashboard"
3. Click the three-dot menu again → "Raw configuration editor"
4. Copy the contents of `dashboards/antigravity_usage.yaml` and paste it.
5. Click "Save".

## Credits & Acknowledgments

This integration is developed and maintained by **David Torres-Mendoza**. 

It is based on the excellent work of the original [hass-claude-usage](https://github.com/trickv/hass-claude-usage) repository by **Patrick van Staveren** (@trickv).

## License

MIT License - see [LICENSE](LICENSE) for details.

