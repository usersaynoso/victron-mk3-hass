from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from typing import Awaitable, Callable

from . import Context
from .battery_monitor_settings import (
    DISABLE_WAVE_CHECK_FLAG_BIT,
    DISABLE_WAVE_CHECK_INVERTED_FLAG_BIT,
    DYNAMIC_CURRENT_LIMITER_ENABLED_FLAG_BIT,
    FLAGS0_SETTING_ID,
    FLAGS1_SETTING_ID,
    POWER_ASSIST_ENABLED_FLAG_BIT,
    setting_flag_enabled,
    setting_flag_supported,
    ups_function_enabled,
    ups_function_supported,
    WEAK_AC_INPUT_ENABLED_FLAG_BIT,
)
from .const import (
    DOMAIN,
    KEY_CONTEXT,
)
from .remote_panel import charger_enabled_in_mode, mode_with_charger_enabled


class VictronMK3StandbySwitchEntity(RestoreEntity, SwitchEntity):
    _attr_has_entity_name = True

    entity_description = SwitchEntityDescription(
        key="remote_panel_standby",
        name="Remote Panel Standby",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, context: Context):
        self.context = context
        self._attr_device_info = context.device_info
        self._attr_unique_id = f"{context.device_id}-{VictronMK3StandbySwitchEntity.entity_description.key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        self._attr_is_on = state.state == STATE_ON if state is not None else True
        await self._notify_controller()

    async def async_turn_on(self) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        await self._notify_controller()

    async def async_turn_off(self) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
        await self._notify_controller()

    async def _notify_controller(self) -> None:
        self.context.controller.standby = self._attr_is_on
        await self.context.coordinator.async_request_refresh()


class VictronMK3BatteryMonitorSwitchEntity(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    entity_description = SwitchEntityDescription(
        key="battery_monitor",
        name="Battery Monitor",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, context: Context):
        CoordinatorEntity.__init__(
            self,
            context.coordinator,
            VictronMK3BatteryMonitorSwitchEntity.entity_description.key,
        )
        self.context = context
        self._attr_device_info = context.device_info
        self._attr_unique_id = (
            f"{context.device_id}-"
            f"{VictronMK3BatteryMonitorSwitchEntity.entity_description.key}"
        )
        self._attr_available = False
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        value = None if data is None else data.battery_monitor_enabled
        if value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = value
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self.context.controller.set_battery_monitor_enabled(True)
        await self.context.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.context.controller.set_battery_monitor_enabled(False)
        await self.context.coordinator.async_request_refresh()


async def set_charge_enabled(context: Context, enabled: bool) -> None:
    data = context.coordinator.data
    if data is None or data.config is None:
        raise HomeAssistantError("Device is not available")

    mode = data.remote_panel_mode()
    if mode is None:
        raise HomeAssistantError("Device is not available")

    await context.controller.set_remote_panel_state(
        mode_with_charger_enabled(mode, enabled),
        data.config.actual_current_limit,
    )
    await context.coordinator.async_request_refresh()


async def set_power_assist_enabled(context: Context, enabled: bool) -> None:
    await context.controller.set_power_assist_enabled(enabled)
    await context.coordinator.async_request_refresh()


async def set_ups_function_enabled(context: Context, enabled: bool) -> None:
    await context.controller.set_ups_function_enabled(enabled)
    await context.coordinator.async_request_refresh()


async def set_dynamic_current_limiter_enabled(context: Context, enabled: bool) -> None:
    await context.controller.set_dynamic_current_limiter_enabled(enabled)
    await context.coordinator.async_request_refresh()


async def set_weak_ac_input_enabled(context: Context, enabled: bool) -> None:
    await context.controller.set_weak_ac_input_enabled(enabled)
    await context.coordinator.async_request_refresh()


@dataclass(kw_only=True)
class VictronMK3SettingFlagSwitchEntityDescription(SwitchEntityDescription):
    setting_id: int
    flag_bit: int
    set_fn: Callable[[Context, bool], Awaitable[None]]


class VictronMK3ChargeEnabledSwitchEntity(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    entity_description = SwitchEntityDescription(
        key="charge_enabled",
        name="Charge Enabled",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, context: Context):
        CoordinatorEntity.__init__(
            self,
            context.coordinator,
            VictronMK3ChargeEnabledSwitchEntity.entity_description.key,
        )
        self.context = context
        self._attr_device_info = context.device_info
        self._attr_unique_id = (
            f"{context.device_id}-"
            f"{VictronMK3ChargeEnabledSwitchEntity.entity_description.key}"
        )
        self._attr_available = False
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        mode = None if data is None else data.remote_panel_mode()
        if mode is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = charger_enabled_in_mode(mode)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await set_charge_enabled(self.context, True)

    async def async_turn_off(self) -> None:
        await set_charge_enabled(self.context, False)


class VictronMK3UpsFunctionSwitchEntity(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    entity_description = SwitchEntityDescription(
        key="ups_function",
        name="UPS Function",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(self, context: Context):
        CoordinatorEntity.__init__(
            self,
            context.coordinator,
            VictronMK3UpsFunctionSwitchEntity.entity_description.key,
        )
        self.context = context
        self._attr_device_info = context.device_info
        self._attr_unique_id = (
            f"{context.device_id}-"
            f"{VictronMK3UpsFunctionSwitchEntity.entity_description.key}"
        )
        self._attr_available = False
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        info = None if data is None else data.setting_info.get(FLAGS0_SETTING_ID)
        value = None if data is None else data.setting_values.get(FLAGS0_SETTING_ID)
        is_on = ups_function_enabled(value)
        if not ups_function_supported(info) or is_on is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await set_ups_function_enabled(self.context, True)

    async def async_turn_off(self) -> None:
        await set_ups_function_enabled(self.context, False)


SETTING_FLAG_ENTITY_DESCRIPTIONS: tuple[VictronMK3SettingFlagSwitchEntityDescription, ...] = (
    VictronMK3SettingFlagSwitchEntityDescription(
        key="power_assist",
        name="PowerAssist",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        setting_id=FLAGS0_SETTING_ID,
        flag_bit=POWER_ASSIST_ENABLED_FLAG_BIT,
        set_fn=set_power_assist_enabled,
    ),
    VictronMK3SettingFlagSwitchEntityDescription(
        key="dynamic_current_limiter",
        name="Dynamic Current Limiter",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        setting_id=FLAGS1_SETTING_ID,
        flag_bit=DYNAMIC_CURRENT_LIMITER_ENABLED_FLAG_BIT,
        set_fn=set_dynamic_current_limiter_enabled,
    ),
    VictronMK3SettingFlagSwitchEntityDescription(
        key="weak_ac_input",
        name="Weak AC Input",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        setting_id=FLAGS0_SETTING_ID,
        flag_bit=WEAK_AC_INPUT_ENABLED_FLAG_BIT,
        set_fn=set_weak_ac_input_enabled,
    ),
)


class VictronMK3SettingFlagSwitchEntity(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        context: Context,
        entity_description: VictronMK3SettingFlagSwitchEntityDescription,
    ):
        CoordinatorEntity.__init__(
            self,
            context.coordinator,
            entity_description.key,
        )
        self.context = context
        self.entity_description = entity_description
        self._attr_device_info = context.device_info
        self._attr_unique_id = f"{context.device_id}-{entity_description.key}"
        self._attr_available = False
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        info = (
            None
            if data is None
            else data.setting_info.get(self.entity_description.setting_id)
        )
        value = (
            None
            if data is None
            else data.setting_values.get(self.entity_description.setting_id)
        )
        is_on = setting_flag_enabled(value, self.entity_description.flag_bit)
        if (
            not setting_flag_supported(info, self.entity_description.flag_bit)
            or is_on is None
        ):
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self.entity_description.set_fn(self.context, True)

    async def async_turn_off(self) -> None:
        await self.entity_description.set_fn(self.context, False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    context = hass.data[DOMAIN][entry.entry_id][KEY_CONTEXT]
    async_add_entities(
        [
            VictronMK3StandbySwitchEntity(context),
            VictronMK3BatteryMonitorSwitchEntity(context),
            VictronMK3ChargeEnabledSwitchEntity(context),
            VictronMK3UpsFunctionSwitchEntity(context),
            *(
                VictronMK3SettingFlagSwitchEntity(context, description)
                for description in SETTING_FLAG_ENTITY_DESCRIPTIONS
            ),
        ]
    )
