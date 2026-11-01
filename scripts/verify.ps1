param([ValidateSet('f2', 'f3', 'f4', 'release')][string]$Phase = 'release')
$ErrorActionPreference = 'Stop'
$reportPath = Join-Path $PSScriptRoot "../docs/reports/$Phase-validation.txt"
"$($Phase.ToUpper()) — verificação local — 31/10/2026" | Set-Content -LiteralPath $reportPath -Encoding utf8
function Invoke-Check {
    param([string]$Name, [scriptblock]$Action)
    "`nComando: $Name" | Tee-Object -FilePath $reportPath -Append
    & $Action 2>&1 | Tee-Object -FilePath $reportPath -Append
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $Name ($LASTEXITCODE)" }
    'Resultado: PASS' | Tee-Object -FilePath $reportPath -Append
}
Push-Location (Join-Path $PSScriptRoot '..')
try {
    Invoke-Check 'ruff check backend tests scripts' { .venv/Scripts/ruff.exe check backend tests scripts }
    Invoke-Check 'ruff format --check backend tests scripts' { .venv/Scripts/ruff.exe format --check backend tests scripts }
    Invoke-Check 'mypy backend' { .venv/Scripts/mypy.exe backend }
    Invoke-Check 'bandit -r backend -q' { .venv/Scripts/bandit.exe -r backend -q }
    Invoke-Check 'python scripts/check_secrets.py' { .venv/Scripts/python.exe scripts/check_secrets.py }
    Invoke-Check 'npm --prefix frontend run lint' { npm --prefix frontend run lint }
    Invoke-Check 'npm --prefix frontend run build' { npm --prefix frontend run build }
    Invoke-Check 'npm --prefix frontend test' { npm --prefix frontend test }
    Invoke-Check 'git diff --check' { git diff --check }
} finally { Pop-Location }
