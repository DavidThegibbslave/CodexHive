param(
  [string]$Command = "$env:SYSTEMROOT\System32\wsl.exe",
  [string[]]$Arguments = @('-e','python3','/mnt/c/codexhive/mcp/codexctl-mcp.py'),
  [string]$LogPath = 'C:\codexhive\mcp\codexctl-wrapper.log'
)
$ErrorActionPreference = 'Stop'

function Write-WrapperLog {
  param([string]$Message)
  try {
    $timestamp = (Get-Date).ToString('s')
    $line = "${timestamp}Z`t$Message"
    $folder = Split-Path -Parent $LogPath
    if (-not [string]::IsNullOrEmpty($folder) -and -not (Test-Path $folder)) {
      New-Item -Path $folder -ItemType Directory -Force | Out-Null
    }
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
  } catch {
    Write-Warning "Failed to write wrapper log: $_"
  }
}

Write-WrapperLog "Launching '$Command' with arguments: $($Arguments -join ' ')"
try {
  & $Command @Arguments
  $exitCode = $LASTEXITCODE
  Write-WrapperLog "codexctl child exited with code $exitCode"
  exit $exitCode
} catch {
  Write-WrapperLog "Wrapper failed: $_"
  $host.ui.WriteErrorLine($_)
  exit 1
}
