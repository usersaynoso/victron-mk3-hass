from pathlib import Path


def test_sensor_source_exposes_battery_energy_entities_for_energy_dashboard() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "victron_mk3"
        / "sensor.py"
    ).read_text()

    assert 'key="battery_energy_into"' in source
    assert 'key="battery_energy_out_of"' in source
    assert "SensorDeviceClass.ENERGY" in source
    assert "SensorStateClass.TOTAL_INCREASING" in source
    assert "UnitOfEnergy.KILO_WATT_HOUR" in source
