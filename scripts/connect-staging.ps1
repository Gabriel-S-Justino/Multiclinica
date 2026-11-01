# Run deliberately in your interactive terminal; authentication opens your browser.
# This script does not create projects, databases, environments, or deployments.
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$vercelCommand = Join-Path $workspacePath '.tools/deploy-cli/node_modules/.bin/vercel.cmd'
$neonCommand = Join-Path $workspacePath '.tools/deploy-cli/node_modules/.bin/neon.cmd'
if (!(Test-Path -LiteralPath $vercelCommand) -or !(Test-Path -LiteralPath $neonCommand)) {
    throw 'As ferramentas locais de implantação não foram encontradas.'
}

function Test-VercelSignedIn {
    param($State)
    # Authenticated output contains username/team; loggedIn only appears when false.
    return $null -ne $State -and ($State.loggedIn -eq $true -or ![string]::IsNullOrWhiteSpace($State.username))
}

Push-Location -LiteralPath $workspacePath
try {
    $vercelState = & $vercelCommand whoami --non-interactive --json | ConvertFrom-Json
    # whoami returns exit 1 with valid {loggedIn:false} when login is needed.
    # That is the expected unauthenticated state, not a failed preflight.
    if ($null -eq $vercelState -or (!$vercelState.PSObject.Properties['loggedIn'] -and [string]::IsNullOrWhiteSpace($vercelState.username))) {
        throw 'A CLI Vercel não retornou um estado de autenticação reconhecido.'
    }
    if (!(Test-VercelSignedIn $vercelState)) {
        Write-Host 'Entre na conta Vercel pelo navegador quando solicitado.'
        & $vercelCommand login
        if ($LASTEXITCODE -ne 0) { throw 'Login Vercel não concluído.' }
    }
    $vercelState = & $vercelCommand whoami --non-interactive --json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !(Test-VercelSignedIn $vercelState)) {
        throw 'Vercel ainda sem autenticação. Nenhum recurso remoto foi criado.'
    }

    $neonProfiles = @(& $neonCommand profile list -o json | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível verificar os perfis Neon.' }
    $authenticatedProfiles = @($neonProfiles | Where-Object { $_.account -and $_.account -ne '-' -and $_.file -ne 'missing' })
    if ($authenticatedProfiles.Count -eq 0) {
        Write-Host 'Entre na conta Neon pelo navegador quando solicitado.'
        & $neonCommand login
        if ($LASTEXITCODE -ne 0) { throw 'Login Neon não concluído.' }
    }
    $neonProfiles = @(& $neonCommand profile list -o json | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível confirmar o login Neon.' }
    $authenticatedProfiles = @($neonProfiles | Where-Object { $_.account -and $_.account -ne '-' -and $_.file -ne 'missing' })
    if ($authenticatedProfiles.Count -eq 0) { throw 'Neon ainda sem perfil autenticado.' }
    Write-Host 'Logins verificados, sem exibir credenciais. Volte ao chat e informe: pronto.'
} finally {
    Pop-Location
}
