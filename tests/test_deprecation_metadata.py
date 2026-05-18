from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLACEMENT_REPO = "https://github.com/usersaynoso/victron-vebus-mk3-control"


def test_readme_directs_users_to_replacement_repository() -> None:
    readme = (ROOT / "README.md").read_text()

    assert "This repository should not be used" in readme
    assert REPLACEMENT_REPO in readme
    assert "Remove this old custom repository from HACS" in readme
    assert "Victron VE.Bus MK3 Control" in readme
    assert "victron_mk3.set_remote_panel_state" in readme
    assert "victron_vebus_mk3.set_remote_panel_state" in readme


def test_hacs_metadata_marks_repository_as_deprecated() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text())

    assert hacs == {
        "name": "Victron MK3 (Deprecated)",
        "render_readme": True,
    }


def test_manifest_points_users_to_replacement_repository() -> None:
    manifest = json.loads(
        (ROOT / "custom_components" / "victron_mk3" / "manifest.json").read_text()
    )

    assert manifest["name"] == "Victron MK3 (Deprecated)"
    assert manifest["documentation"] == f"{REPLACEMENT_REPO}/"
    assert manifest["issue_tracker"] == f"{REPLACEMENT_REPO}/issues"
    assert manifest["version"] == "0.6.1"
