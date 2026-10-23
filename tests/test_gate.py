"""
Unit and integration tests for env-sync-gate.
"""

import pytest
from pathlib import Path
from env_sync_gate.core import EnvSyncGate, EnvVarUsage
from env_sync_gate.monetization import LicenseManager
from env_sync_gate.cli import main

def test_license_manager():
    comm = LicenseManager.get_tier(None)
    assert comm["tier"] == "community"

    ent = LicenseManager.get_tier("ord_ent_env_sync")
    assert ent["tier"] == "enterprise"

    banner = LicenseManager.get_banner("env-sync-gate")
    assert "GABFQIK63R2NETJM7T673EAMZN4RJLLGP3OFUEJU5ZVTGWUKULZJNL6" in banner

def test_python_env_scanner(tmp_path):
    gate = EnvSyncGate()
    code = """
import os

key = os.environ["STRIPE_KEY"]
timeout = os.getenv("TIMEOUT_SECONDS", "30")
db_url = os.environ.get("DATABASE_URL")
"""
    f = str(tmp_path / "app.py")
    gate.scan_python(f, code)

    names = {u.name: u for u in gate.usages}
    assert "STRIPE_KEY" in names
    assert names["STRIPE_KEY"].is_required is True

    assert "TIMEOUT_SECONDS" in names
    assert names["TIMEOUT_SECONDS"].has_default is True

    assert "DATABASE_URL" in names

def test_dict_get_not_treated_as_env_and_direct_environ(tmp_path):
    gate = EnvSyncGate()
    code = """
from os import environ
normal_dict = {"foo": "bar"}
val = normal_dict.get("foo") # Should NOT be treated as env var!
direct_env = environ["DIRECT_SECRET_KEY"]
"""
    f = str(tmp_path / "dict_test.py")
    gate.scan_python(f, code)

    names = {u.name: u for u in gate.usages}
    # normal_dict.get("foo") MUST NOT be detected
    assert "foo" not in names
    # DIRECT_SECRET_KEY MUST be detected
    assert "DIRECT_SECRET_KEY" in names
    assert names["DIRECT_SECRET_KEY"].is_required is True

def test_ts_env_scanner(tmp_path):
    gate = EnvSyncGate()
    code = """
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const secret = process.env["SECRET_TOKEN"];
const fallback = process.env.PORT || "3000";
"""
    f = str(tmp_path / "config.ts")
    gate.scan_js_ts(f, code)

    names = {u.name: u for u in gate.usages}
    assert "NEXT_PUBLIC_API_URL" in names
    assert "SECRET_TOKEN" in names
    assert "PORT" in names
    assert names["PORT"].has_default is True

def test_audit_missing_and_dead_vars(tmp_path):
    code_file = tmp_path / "server.py"
    code_file.write_text("import os; val = os.environ['REDIS_URL']\n", encoding="utf-8")

    template_file = tmp_path / ".env.example"
    template_file.write_text("DATABASE_URL=postgres://...\n", encoding="utf-8")

    violations, discovered = EnvSyncGate.scan_directory(str(tmp_path), str(template_file))
    kinds = [v.kind for v in violations]

    # REDIS_URL is in code but missing from template
    assert "CRITICAL_STARTUP_CRASH" in kinds
    # DATABASE_URL is in template but not in code
    assert "DEAD_CONFIG_VAR" in kinds

def test_cli_execution(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("import os; print(os.getenv('PORT', '8080'))\n", encoding="utf-8")

    # Generate template
    out_tmpl = tmp_path / ".env.example"
    exit_gen = main(["generate-template", "--path", str(tmp_path), "--out", str(out_tmpl)])
    assert exit_gen == 0
    assert "PORT=" in out_tmpl.read_text(encoding="utf-8")

    # Scan with generated template
    exit_scan = main(["scan", "--path", str(tmp_path), "--template", str(out_tmpl)])
    assert exit_scan == 0

    exit_lic = main(["license"])
    assert exit_lic == 0

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
