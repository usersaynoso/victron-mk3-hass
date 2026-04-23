from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from typing import Awaitable, Callable

from . import Context, Data
from .battery_monitor_settings import (
    BATTERY_CAPACITY_SETTING_ID,
    BATTERY_CHARGE_EFFICIENCY_SETTING_ID,
    BATTERY_SOC_WHEN_BULK_FINISHED_SETTING_ID,
    DC_INPUT_LOW_RESTART_OFFSET_SETTING_ID,
    DC_INPUT_LOW_SHUTDOWN_SETTING_ID,
    numeric_setting_range,
    relative_numeric_setting_range,
    relative_setting_offset_from_absolute,
)
from .const import (
    DOMAIN,
    KEY_CONTEXT,
)


async def set_remote_panel_current_limit(context: Context, value: float) -> None:
    data = context.coordinator.data
    if data is None or data.config is None:
        raise HomeAssistantError("Device is not available")

    mode = data.remote_panel_mode()
    if mode is None:
        raise HomeAssistantError("Device is not available")
    await context.controller.set_remote_panel_state(mode, value)
    await context.coordinator.async_request_refresh()


async def set_battery_monitor_setting(
    context: Context, setting_id: int, value: float
) -> None:
    await context.controller.set_setting(setting_id, value)
    await context.coordinator.async_request_refresh()


async def set_dc_input_low_restart(context: Context, absolute_value: float) -> None:
    data = context.coordinator.data
    shutdown_value = (
        None
        if data is None
        else relative_setting_base_value(data, DC_INPUT_LOW_SHUTDOWN_SETTING_ID)
    )
    if shutdown_value is None:
        raise HomeAssistantError("Device is not available")

    await context.controller.set_setting(
        DC_INPUT_LOW_RESTART_OFFSET_SETTING_ID,
        relative_setting_offset_from_absolute(shutdown_value, absolute_value),
    )
    await context.coordinator.async_request_refresh()


@dataclass(kw_only=True)
class VictronMK3NumberEntityDescription(NumberEntityDescription):
    range_fn: Callable[[Data], tuple[float, float, float, float]]
    set_fn: Callable[[Context, float], Awaitable[None]]


ENTITY_DESCRIPTIONS: tuple[VictronMK3NumberEntityDescription, ...] = (
    VictronMK3NumberEntityDescription(
        key="remote_panel_current_limit",
        name="Remote Panel Current Limit",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: None
        if data.config is None
        else (
            data.config.minimum_current_limit,
            data.config.maximum_current_limit,
            0.1,
            data.config.actual_current_limit,
        ),
        set_fn=set_remote_panel_current_limit,
    ),
    VictronMK3NumberEntityDescription(
        key="battery_capacity",
        name="Battery Capacity",
        native_unit_of_measurement="Ah",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: setting_range(data, BATTERY_CAPACITY_SETTING_ID),
        set_fn=lambda context, value: set_battery_monitor_setting(
            context, BATTERY_CAPACITY_SETTING_ID, value
        ),
    ),
    VictronMK3NumberEntityDescription(
        key="battery_soc_when_bulk_finished",
        name="State of Charge When Bulk Finished",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: setting_range(
            data, BATTERY_SOC_WHEN_BULK_FINISHED_SETTING_ID
        ),
        set_fn=lambda context, value: set_battery_monitor_setting(
            context, BATTERY_SOC_WHEN_BULK_FINISHED_SETTING_ID, value
        ),
    ),
    VictronMK3NumberEntityDescription(
        key="battery_charge_efficiency",
        name="Charge Efficiency",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: setting_range(
            data, BATTERY_CHARGE_EFFICIENCY_SETTING_ID
        ),
        set_fn=lambda context, value: set_battery_monitor_setting(
            context, BATTERY_CHARGE_EFFICIENCY_SETTING_ID, value
        ),
    ),
    VictronMK3NumberEntityDescription(
        key="dc_input_low_shutdown",
        name="DC Input Low Shut-down",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: setting_range(data, DC_INPUT_LOW_SHUTDOWN_SETTING_ID),
        set_fn=lambda context, value: set_battery_monitor_setting(
            context, DC_INPUT_LOW_SHUTDOWN_SETTING_ID, value
        ),
    ),
    VictronMK3NumberEntityDescription(
        key="dc_input_low_restart",
        name="DC Input Low Restart",
        device_class=NumberDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        range_fn=lambda data: dc_input_low_restart_range(data),
        set_fn=set_dc_input_low_restart,
    ),
)


def setting_range(
    data: Data, setting_id: int
) -> tuple[float, float, float, float] | None:
    return numeric_setting_range(
        data.setting_info.get(setting_id),
        data.setting_values.get(setting_id),
    )


def relative_setting_base_value(data: Data, setting_id: int) -> float | None:
    value = data.setting_values.get(setting_id)
    if value is None or not value.supported:
        return None
    return value.value


def dc_input_low_restart_range(data: Data) -> tuple[float, float, float, float] | None:
    return relative_numeric_setting_range(
        relative_setting_base_value(data, DC_INPUT_LOW_SHUTDOWN_SETTING_ID),
        data.setting_info.get(DC_INPUT_LOW_RESTART_OFFSET_SETTING_ID),
        data.setting_values.get(DC_INPUT_LOW_RESTART_OFFSET_SETTING_ID),
    )


class VictronMK3NumberEntity(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self, context: Context, entity_description: VictronMK3NumberEntityDescription
    ):
        CoordinatorEntity.__init__(self, context.coordinator, entity_description.key)
        self.context = context
        self.entity_description = entity_description
        self._attr_device_info = context.device_info
        self._attr_unique_id = f"{context.device_id}-{entity_description.key}"
        self._attr_available = False
        self._attr_native_min_value = 0
        self._attr_native_max_value = 0
        self._attr_native_step = None
        self._attr_native_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        value = None if data is None else self.entity_description.range_fn(data)
        if value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_min_value = value[0]
            self._attr_native_max_value = value[1]
            self._attr_native_step = value[2]
            self._attr_native_value = value[3]
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.context, value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    context = hass.data[DOMAIN][entry.entry_id][KEY_CONTEXT]
    async_add_entities(
        VictronMK3NumberEntity(context, description)
        for description in ENTITY_DESCRIPTIONS
    )
