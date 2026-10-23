"""
Static scanner for process.env and os.environ preventing missing environment variable crashes in production deployments.
"""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

@dataclass
class EnvVarUsage:
    name: str
    file_path: str
    line: int
    is_required: bool  # True if indexing os.environ["VAR"] or process.env.VAR without fallback
    has_default: bool

@dataclass
class EnvViolation:
    var_name: str
    kind: str  # MISSING_IN_TEMPLATE, CRITICAL_STARTUP_CRASH, DEAD_CONFIG_VAR
    severity: str  # CRITICAL, WARNING, INFO
    file_path: str
    line: int
    description: str
    remediation: str

class EnvSyncGate:
    def __init__(self):
        self.usages: List[EnvVarUsage] = []

    def scan_python(self, file_path: str, content: str) -> None:
        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            # 1. os.environ["VAR"] or environ["VAR"]
            if isinstance(node, ast.Subscript):
                is_environ_sub = False
                if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
                    is_environ_sub = True
                elif isinstance(node.value, ast.Name) and node.value.id == "environ":
                    is_environ_sub = True

                if is_environ_sub and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    self.usages.append(EnvVarUsage(
                        name=node.slice.value,
                        file_path=file_path,
                        line=node.lineno,
                        is_required=True,
                        has_default=False
                    ))
            elif isinstance(node, ast.Call):
                # 2. os.getenv("FOO", "default"), getenv("FOO"), or (os.)environ.get("FOO")
                is_getenv = False
                if isinstance(node.func, ast.Name) and node.func.id == "getenv":
                    is_getenv = True
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr == "getenv" and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                        is_getenv = True
                    elif node.func.attr == "get":
                        # Must be environ.get() or os.environ.get()
                        if isinstance(node.func.value, ast.Name) and node.func.value.id == "environ":
                            is_getenv = True
                        elif isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "environ":
                            is_getenv = True

                if is_getenv and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    var_name = node.args[0].value
                    has_default = len(node.args) > 1 or any(kw.arg == "default" for kw in node.keywords)
                    self.usages.append(EnvVarUsage(
                        name=var_name,
                        file_path=file_path,
                        line=node.lineno,
                        is_required=not has_default,
                        has_default=has_default
                    ))

    def scan_js_ts(self, file_path: str, content: str) -> None:
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            # process.env.VAR_NAME or import.meta.env.VAR_NAME
            matches_dot = re.findall(r"\b(?:process\.env|import\.meta\.env)\.([A-Z0-9_]+)\b", line)
            for var in matches_dot:
                # check if there is || "default" or ?? "default"
                has_default = bool(re.search(rf"\b{var}\b\s*(?:\|\||\?\?)\s*['\"]", line))
                self.usages.append(EnvVarUsage(
                    name=var,
                    file_path=file_path,
                    line=idx,
                    is_required=not has_default,
                    has_default=has_default
                ))

            # process.env["VAR_NAME"]
            matches_bracket = re.findall(r"\b(?:process\.env|import\.meta\.env)\[['\"]([A-Z0-9_]+)['\"]\]", line)
            for var in matches_bracket:
                has_default = bool(re.search(rf"\[['\"]{var}['\"]\]\s*(?:\|\||\?\?)\s*['\"]", line))
                self.usages.append(EnvVarUsage(
                    name=var,
                    file_path=file_path,
                    line=idx,
                    is_required=not has_default,
                    has_default=has_default
                ))

    @staticmethod
    def parse_env_template(template_path: str) -> Set[str]:
        p = Path(template_path)
        if not p.exists():
            return set()
        vars_found: Set[str] = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # KEY=VALUE or KEY=
            match = re.match(r"^([A-Z0-9_]+)\s*=", line)
            if match:
                vars_found.add(match.group(1))
        return vars_found

    def audit(self, template_vars: Set[str]) -> List[EnvViolation]:
        violations: List[EnvViolation] = []
        code_vars: Set[str] = {u.name for u in self.usages}

        # Check undeclared variables
        for u in self.usages:
            if u.name not in template_vars:
                sev = "CRITICAL" if u.is_required else "WARNING"
                kind = "CRITICAL_STARTUP_CRASH" if u.is_required else "MISSING_IN_TEMPLATE"
                violations.append(EnvViolation(
                    var_name=u.name,
                    kind=kind,
                    severity=sev,
                    file_path=u.file_path,
                    line=u.line,
                    description=f"Environment variable '{u.name}' is referenced in {u.file_path}:{u.line} but missing from template (.env.example).",
                    remediation=f"Add '{u.name}=...' to .env.example with descriptive documentation."
                ))

        # Check dead template variables
        for tvar in template_vars:
            if tvar not in code_vars:
                violations.append(EnvViolation(
                    var_name=tvar,
                    kind="DEAD_CONFIG_VAR",
                    severity="INFO",
                    file_path=".env.example",
                    line=1,
                    description=f"Template variable '{tvar}' is declared in .env.example but never accessed anywhere in the codebase.",
                    remediation=f"Remove '{tvar}' from .env.example if obsolete, or verify usage."
                ))

        return violations

    @classmethod
    def scan_directory(cls, directory: str, template_path: Optional[str] = None) -> Tuple[List[EnvViolation], Set[str]]:
        gate = cls()
        dir_path = Path(directory)

        # Find template
        actual_template = None
        if template_path:
            actual_template = template_path
        else:
            for cand in [".env.example", ".env.template", ".env.sample"]:
                if (dir_path / cand).exists():
                    actual_template = str(dir_path / cand)
                    break

        template_vars = cls.parse_env_template(actual_template) if actual_template else set()

        for file in dir_path.rglob("*"):
            if not file.is_file():
                continue
            parts = file.parts
            if any(p.startswith(".") or p in {"node_modules", "venv", ".git", "__pycache__", "dist", "build"} for p in parts):
                continue
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                if file.suffix == ".py":
                    gate.scan_python(str(file), content)
                elif file.suffix in {".ts", ".js", ".tsx", ".jsx"}:
                    gate.scan_js_ts(str(file), content)
            except Exception:
                continue

        violations = gate.audit(template_vars)
        discovered = {u.name for u in gate.usages}
        return violations, discovered

    @staticmethod
    def generate_template_content(vars_set: Set[str]) -> str:
        lines = [
            "# =============================================================================",
            "# AUTO-GENERATED ENVIRONMENT CONFIGURATION TEMPLATE",
            "# Generated by env-sync-gate (OrderStream Developer Suite)",
            "# =============================================================================",
            ""
        ]
        for v in sorted(vars_set):
            lines.append(f"{v}=")
        return "\n".join(lines) + "\n"
