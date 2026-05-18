# Victron MK3 Has Been Superseded

This repository should not be used for new installations or future updates.

Use **Victron VE.Bus MK3 Control** instead:

https://github.com/usersaynoso/victron-vebus-mk3-control

The replacement integration is the maintained version of this Home Assistant
integration for local Victron VE.Bus MK3-USB monitoring and control.

## What To Do

If you installed this repository through HACS:

1. Remove this old custom repository from HACS:
   `https://github.com/usersaynoso/victron-mk3-hass`
2. Add the replacement custom repository in HACS:
   `https://github.com/usersaynoso/victron-vebus-mk3-control`
3. Install **Victron VE.Bus MK3 Control**.
4. Restart Home Assistant.
5. Add **Victron VE.Bus MK3 Control** from Settings -> Devices & services.

The replacement integration uses a different Home Assistant domain:
`victron_vebus_mk3`.

If you have dashboards, scripts, automations, or service calls that reference
the old `victron_mk3` integration, update those references manually after
installing the replacement integration. For example, the old
`victron_mk3.set_remote_panel_state` service is replaced by
`victron_vebus_mk3.set_remote_panel_state`.

Open issues and future development should use the replacement repository:

https://github.com/usersaynoso/victron-vebus-mk3-control/issues
