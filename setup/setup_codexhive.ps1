param(
  [string]$ServerName = 'codexhive',
  [string]$ScriptPath = 'C:\\codexhive\\mcp\\codexctl-mcp.ps1',
  [switch]$BypassExecutionPolicy
)
$ErrorActionPreference = 'Stop'

# Use a different var name to avoid clobbering PowerShell's $HOME automatic variable
$userProfile = [Environment]::GetFolderPath('UserProfile')
$codexDir = Join-Path $userProfile '.codex'
$config = Join-Path $codexDir 'config.toml'

if (-not (Test-Path $codexDir)) { [IO.Directory]::CreateDirectory($codexDir) | Out-Null }
if (-not (Test-Path $config)) { New-Item -ItemType File -Path $config | Out-Null }

$toml = Get-Content -LiteralPath $config -Raw -ErrorAction SilentlyContinue
$entryHeader = "[mcp_servers.$ServerName]"
$updated = $false
$featurePattern = '(?ms)^\[features\]\s*(.*?)(?=^\[|\Z)'
$featuresMatch = [regex]::Match($toml, $featurePattern)

if (-not $featuresMatch.Success) {
  if ($toml -and -not $toml.EndsWith("`n")) {
    $toml += "`n"
  }
  $toml += "`n[features]`nrmcp_client = true`n"
  $updated = $true
  Write-Host "Added [features] block with rmcp_client = true"
} elseif ($featuresMatch.Value -notmatch 'rmcp_client\s*=') {
  $block = $featuresMatch.Value
  if (-not $block.EndsWith("`n")) {
    $block += "`n"
  }
  $block += "rmcp_client = true`n"
  $prefix = $toml.Substring(0, $featuresMatch.Index)
  $suffix = $toml.Substring($featuresMatch.Index + $featuresMatch.Length)
  $toml = $prefix + $block + $suffix
  $updated = $true
  Write-Host "Appended rmcp_client = true to existing [features] block"
}

# Build args list depending on ExecutionPolicy needs
if ($BypassExecutionPolicy) {
  $argsList = '["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "' + ($ScriptPath -replace '\\','\\\\') + '"]'
} else {
  $argsList = '["-NoProfile", "-File", "' + ($ScriptPath -replace '\\','\\\\') + '"]'
}

if ($toml -notmatch [regex]::Escape($entryHeader)) {
  $block = @"

[mcp_servers.$ServerName]
command = "pwsh"
args = $argsList
startup_timeout_sec = 30
"@
  if ($toml -and -not $toml.EndsWith("`n")) {
    $toml += "`n"
  }
  $toml += "`n$block"
  $updated = $true
  Write-Host "Added MCP server '$ServerName' configuration block"
} else {
  Write-Host "MCP server '$ServerName' already present in $config at $config"
}

if ($updated) {
  Set-Content -LiteralPath $config -Value $toml -Encoding UTF8
  Write-Host "Updated $config"
}

Write-Host "Done. Start 'codex' and run /mcp to verify connection."
