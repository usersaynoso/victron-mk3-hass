from pathlib import Path


def test_setup_entry_refreshes_without_blocking_on_first_update() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "victron_mk3"
        / "__init__.py"
    ).read_text()

    assert "await coordinator.async_refresh()" in source
    assert "async_config_entry_first_refresh" not in source
    assert "debug_scan_settings" not in source
    assert "DEBUG_SCAN_MARKER" not in source
