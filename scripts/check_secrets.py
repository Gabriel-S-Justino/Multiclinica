"""Scan both tracked and untracked non-ignored files without printing secret values."""

import subprocess

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings

paths = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard"], text=True
).splitlines()
with default_settings():
    findings = SecretsCollection()
    for path in paths:
        if path.endswith(("uv.lock", "package-lock.json")):
            continue
        findings.scan_file(path)
    count = sum(len(values) for values in findings.data.values())
    for path, values in findings.data.items():
        for item in values:
            print(f"Possível segredo: {path}:{item.line_number} ({item.type})")
    print(f"Arquivos examinados: {len(paths)}; possíveis segredos: {count}")
    raise SystemExit(1 if count else 0)
