"""
Command line interface for env-sync-gate.
"""

import argparse
import sys
from pathlib import Path
from env_sync_gate.core import EnvSyncGate
from env_sync_gate.monetization import LicenseManager

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="env-sync-gate",
        description="Static scanner for process.env and os.environ preventing production startup crashes"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Scan directory and audit against .env.example")
    scan_parser.add_argument("--path", default=".", help="Directory to scan")
    scan_parser.add_argument("--template", default=None, help="Path to .env.example template file")
    scan_parser.add_argument("--fail-on-missing", action="store_true", default=True, help="Fail if code uses undeclared env vars")
    scan_parser.add_argument("--license-key", default=None, help="OrderStream license key")

    # generate-template command
    gen_parser = subparsers.add_parser("generate-template", help="Extract all environment variables in code and generate .env.example")
    gen_parser.add_argument("--path", default=".", help="Directory to scan")
    gen_parser.add_argument("--out", default=".env.example", help="Output file path")

    # license / donate command
    subparsers.add_parser("license", help="View license tier and 0% fee crypto donation wallets")

    args = parser.parse_args(argv)

    if not args.command or args.command == "license":
        print(LicenseManager.get_banner("env-sync-gate"))
        tier = LicenseManager.get_tier(getattr(args, "license_key", None))
        print(f"Active Tier: {tier['name']} ({tier['tier']})")
        print(f"Features: {', '.join(tier['features'])}")
        print(LicenseManager.get_remediation_footer())
        return 0

    if args.command == "scan":
        print(LicenseManager.get_banner("env-sync-gate"))
        violations, discovered = EnvSyncGate.scan_directory(args.path, args.template)

        criticals = [v for v in violations if v.severity == "CRITICAL"]
        warnings = [v for v in violations if v.severity == "WARNING"]
        deads = [v for v in violations if v.severity == "INFO"]

        print(f"[ENV-SYNC-GATE] Scanned Directory: {args.path}")
        print(f"[ENV-SYNC-GATE] Total Env Variables Found in Code: {len(discovered)}")
        print(f"[ENV-SYNC-GATE] Violations: {len(violations)} (Critical Crashes: {len(criticals)}, Missing: {len(warnings)}, Dead: {len(deads)})")

        for v in violations:
            print(f"\n  [{v.severity}] {v.kind}: {v.var_name}")
            print(f"     Location: {v.file_path}:{v.line}")
            print(f"     Problem:  {v.description}")
            print(f"     Fix:      {v.remediation}")

        print(LicenseManager.get_remediation_footer())

        if args.fail_on_missing and (criticals or warnings):
            print("\n❌ [ENV-SYNC-GATE] FAILED: Missing environment variables detected! Deployment crash imminent.")
            return 1

        print("\n✅ [ENV-SYNC-GATE] PASSED: All environment variables documented and synchronized.")
        return 0

    elif args.command == "generate-template":
        print(LicenseManager.get_banner("env-sync-gate"))
        _, discovered = EnvSyncGate.scan_directory(args.path)
        content = EnvSyncGate.generate_template_content(discovered)
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"✅ [ENV-SYNC-GATE] Successfully generated '{args.out}' with {len(discovered)} variables.")
        print(LicenseManager.get_remediation_footer())
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
