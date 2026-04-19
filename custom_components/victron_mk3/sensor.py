from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from typing import Callable
from victron_mk3 import DeviceState

from . import Context, Data, UPDATE_INTERVAL
from .battery_energy import BatteryEnergyAccumulator, BatteryEnergyDirection
from .const import (
    AC_PHASES_POLLED,
    DOMAIN,
    KEY_CONTEXT,
)
from .remote_panel import Mode, enum_options, enum_value
from .ram_variables import (
    IGNORE_AC_INPUT_VARIABLE_ID,
    ram_variable_bool_enabled,
    ram_variable_bool_supported,
)


@dataclass(kw_only=True)
class VictronMK3SensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[Data], StateType]


@dataclass(kw_only=True)
class VictronMK3BatteryEnergySensorEntityDescription(SensorEntityDescription):
    direction: BatteryEnergyDirection


def make_ac_phase_sensors(phase: int) -> tuple[VictronMK3SensorEntityDescription, ...]:
    index = phase - 1
    enable_default = phase == 1
    key_suffix = "" if phase == 1 else f"_l{phase}"
    name_suffix = "" if phase == 1 else f" L{phase}"
    return (
        VictronMK3SensorEntityDescription(
            key=f"ac_input_voltage{key_suffix}",
            name=f"AC Input Voltage{name_suffix}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=1,
            entity_registry_enabled_default=enable_default,
            value_fn=lambda data: None
            if data.ac[index] is None
            else data.ac[index].ac_mains_voltage,
        ),
        VictronMK3SensorEntityDescription(
            key=f"ac_input_current{key_suffix}",
            name=f"AC Input Current{name_suffix}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=1,
            entity_registry_enabled_default=enable_default,
            value_fn=lambda data: None
            if data.ac[index] is None
            else data.ac[index].ac_mains_current,
        ),
        VictronMK3SensorEntityDescription(
            key=f"ac_output_voltage{key_suffix}",
            name=f"AC Output Voltage{name_suffix}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=1,
            entity_registry_enabled_default=enable_default,
            value_fn=lambda data: None
            if data.ac[index] is None
            else data.ac[index].ac_inverter_voltage,
        ),
        VictronMK3SensorEntityDescription(
            key=f"ac_output_current{key_suffix}",
            name=f"AC Output Current{name_suffix}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=1,
            entity_registry_enabled_default=enable_default,
            value_fn=lambda data: None
            if data.ac[index] is None
            else data.ac[index].ac_inverter_current,
        ),
    )


ENTITY_DESCRIPTIONS: tuple[VictronMK3SensorEntityDescription, ...] = (
    VictronMK3SensorEntityDescription(
        key="ac_input_current_limit",
        name="AC Input Current Limit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None
        if data.config is None
        else data.config.actual_current_limit,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_input_current_limit_maximum",
        name="AC Input Current Limit Maximum",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None
        if data.config is None
        else data.config.maximum_current_limit,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_input_current_limit_minimum",
        name="AC Input Current Limit Minimum",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None
        if data.config is None
        else data.config.minimum_current_limit,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_input_power",
        name="AC Input Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: None if data.power is None else data.power.ac_mains_power,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_input_frequency",
        name="AC Input Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=1,
        value_fn=lambda data: None
        if data.ac[0] is None
        else data.ac[0].ac_mains_frequency,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_output_power",
        name="AC Output Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: None
        if data.power is None
        else data.power.ac_inverter_power,
    ),
    VictronMK3SensorEntityDescription(
        key="ac_output_frequency",
        name="AC Output Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=1,
        value_fn=lambda data: None
        if data.dc is None
        else data.dc.ac_inverter_frequency,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        value_fn=lambda data: None if data.dc is None else data.dc.dc_voltage,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_power",
        name="Battery Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: None if data.power is None else data.power.dc_power,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_charge_discharge_power",
        name="Battery Charge Discharge Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=1,
        value_fn=lambda data: None if data.power is None else -data.power.dc_power,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_state_of_charge",
        name="Battery State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.battery_soc,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_charger_current",
        name="Battery Charger Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda data: None
        if data.dc is None
        else data.dc.dc_current_from_charger,
    ),
    VictronMK3SensorEntityDescription(
        key="battery_inverter_current",
        name="Battery Inverter Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda data: None
        if data.dc is None
        else data.dc.dc_current_to_inverter,
    ),
    VictronMK3SensorEntityDescription(
        key="device_state",
        name="Device State",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(DeviceState),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None
        if data.ac[0] is None
        else enum_value(data.ac[0].device_state),
    ),
    VictronMK3SensorEntityDescription(
        key="firmware_version",
        name="Firmware Version",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None if data.version is None else data.version.version,
    ),
    VictronMK3SensorEntityDescription(
        key="lit_indicators",
        name="Lit Indicators",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None if data.led is None else enum_value(data.led.on),
    ),
    VictronMK3SensorEntityDescription(
        key="blinking_indicators",
        name="Blinking Indicators",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: None if data.led is None else enum_value(data.led.blink),
    ),
    VictronMK3SensorEntityDescription(
        key="front_panel_mode",
        name="Front Panel Mode",
        device_class=SensorDeviceClass.ENUM,
        options=("off", "on", "charger_only"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: enum_value(data.front_panel_mode()),
    ),
    VictronMK3SensorEntityDescription(
        key="ignore_ac_input_state",
        name="Ignore AC Input State",
        device_class=SensorDeviceClass.ENUM,
        options=("off", "on"),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _ignore_ac_input_state(data),
    ),
    VictronMK3SensorEntityDescription(
        key="actual_mode",
        name="Actual Mode",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(Mode),
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: enum_value(data.actual_mode()),
    ),
)


BATTERY_ENERGY_ENTITY_DESCRIPTIONS: tuple[
    VictronMK3BatteryEnergySensorEntityDescription, ...
] = (
    VictronMK3BatteryEnergySensorEntityDescription(
        key="battery_energy_into",
        name="Battery Energy Into",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        direction=BatteryEnergyDirection.INTO_BATTERY,
    ),
    VictronMK3BatteryEnergySensorEntityDescription(
        key="battery_energy_out_of",
        name="Battery Energy Out Of",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
        direction=BatteryEnergyDirection.OUT_OF_BATTERY,
    ),
)


class VictronMK3SensorEntity(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, context: Context, entity_description: VictronMK3SensorEntityDescription
    ):
        CoordinatorEntity.__init__(self, context.coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_device_info = context.device_info
        self._attr_unique_id = f"{context.device_id}-{entity_description.key}"
        self._attr_available = False
        self._attr_native_value = None

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        value = None if data is None else self.entity_description.value_fn(data)
        if value is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = value
        self.async_write_ha_state()


class VictronMK3BatteryEnergySensorEntity(RestoreEntity, CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        context: Context,
        entity_description: VictronMK3BatteryEnergySensorEntityDescription,
    ):
        CoordinatorEntity.__init__(self, context.coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_device_info = context.device_info
        self._attr_unique_id = f"{context.device_id}-{entity_description.key}"
        self._attr_available = False
        self._attr_native_value = None
        self._accumulator = BatteryEnergyAccumulator(
            direction=entity_description.direction,
            max_interval_seconds=UPDATE_INTERVAL.total_seconds() * 3,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            restored_value = _parse_float(last_state.state)
            if restored_value is not None:
                self._accumulator.restore(restored_value)
                self._attr_native_value = round(self._accumulator.total_kwh, 6)
                self._attr_available = True

        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        power_watts = None if data is None or data.power is None else data.power.dc_power

        total_kwh = self._accumulator.advance(dt_util.utcnow(), power_watts)
        if power_watts is None:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_native_value = round(total_kwh, 6)
        self.async_write_ha_state()


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ignore_ac_input_state(data: Data) -> str | None:
    info = data.ram_variable_info.get(IGNORE_AC_INPUT_VARIABLE_ID)
    value = data.ram_variable_values.get(IGNORE_AC_INPUT_VARIABLE_ID)
    if not ram_variable_bool_supported(info):
        return None

    enabled = ram_variable_bool_enabled(value, info)
    if enabled is None:
        return None
    return "on" if enabled else "off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    context = hass.data[DOMAIN][entry.entry_id][KEY_CONTEXT]
    entities = [
        VictronMK3SensorEntity(context, description)
        for description in ENTITY_DESCRIPTIONS
    ]
    entities += [
        VictronMK3BatteryEnergySensorEntity(context, description)
        for description in BATTERY_ENERGY_ENTITY_DESCRIPTIONS
    ]
    for phase in range(1, AC_PHASES_POLLED + 1):
        ac_sensors = [
            VictronMK3SensorEntity(context, description)
            for description in make_ac_phase_sensors(phase)
        ]
        context.controller.ac_entities[phase - 1] += ac_sensors
        entities += ac_sensors
    async_add_entities(entities)
