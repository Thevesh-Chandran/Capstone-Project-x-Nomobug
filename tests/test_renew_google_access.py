"""Renewal checks use only synthetic private files and a mocked browser flow."""

import json
import runpy
from pathlib import Path
from unittest.mock import MagicMock

import dotenv
import pytest
from google_auth_oauthlib.flow import InstalledAppFlow

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "renew_google_access.py"


@pytest.fixture
def setup_renewal(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / "renew_google_access.py"
    script.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    token = secrets / "google_token.json"
    token.write_text("synthetic-old", encoding="utf-8")
    client = secrets / "google_oauth_client.json"
    # Stale exported redirect list must not prevent the confirmed 8081 callback.
    client.write_text(json.dumps({"web": {"redirect_uris": ["http://localhost:8080/"]}}), encoding="utf-8")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args: False)
    monkeypatch.setenv("NOMOBUG_GOOGLE_TOKEN", str(token))
    monkeypatch.setenv("NOMOBUG_GOOGLE_CLIENT_SECRET", str(client))
    flow = MagicMock()
    credentials = flow.run_local_server.return_value
    credentials.valid = True
    credentials.refresh_token = "synthetic-refresh"
    credentials.has_scopes.return_value = True
    credentials.to_json.return_value = "synthetic-new"
    monkeypatch.setattr(InstalledAppFlow, "from_client_config", lambda *args: flow)
    return script, token, flow


def test_success_backs_up_old_and_uses_registered_port(setup_renewal, capsys):
    script, token, flow = setup_renewal
    runpy.run_path(str(script))
    assert token.read_text() == "synthetic-new"
    backups = list(token.parent.glob("*.bak"))
    assert len(backups) == 1 and backups[0].read_text() == "synthetic-old"
    assert flow.run_local_server.call_args.kwargs["port"] == 8081
    assert "synthetic-" not in capsys.readouterr().out


def test_cancel_keeps_original(setup_renewal):
    script, token, flow = setup_renewal
    flow.run_local_server.side_effect = RuntimeError("synthetic-secret")
    with pytest.raises(SystemExit, match="Existing token unchanged") as error:
        runpy.run_path(str(script))
    assert token.read_text() == "synthetic-old"
    assert not list(token.parent.glob("*.bak"))
    assert "synthetic-secret" not in str(error.value)


def test_incomplete_consent_keeps_original(setup_renewal):
    script, token, flow = setup_renewal
    flow.run_local_server.return_value.has_scopes.return_value = False
    with pytest.raises(SystemExit, match="Existing token unchanged"):
        runpy.run_path(str(script))
    assert token.read_text() == "synthetic-old"
