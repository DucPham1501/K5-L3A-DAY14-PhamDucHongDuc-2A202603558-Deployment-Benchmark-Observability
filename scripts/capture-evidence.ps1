param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Name
)
$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent $PSScriptRoot
[IO.Directory]::CreateDirectory((Join-Path $repoPath 'screenshots')) | Out-Null
$imagePath = Join-Path (Join-Path $repoPath 'screenshots') $Name
$browserProfile = Join-Path $repoPath '.tools/edge-evidence-profile'
$edgeExecutable = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$browserArguments = @('--headless', '--disable-gpu', '--no-first-run', '--hide-scrollbars', '--disable-extensions',
    "--user-data-dir=`"$browserProfile`"", '--window-size=1700,1300',
    '--virtual-time-budget=15000', "--screenshot=`"$imagePath`"", "`"$Url`"")
Start-Process -FilePath $edgeExecutable -ArgumentList $browserArguments -Wait -WindowStyle Hidden
if (-not (Test-Path -LiteralPath $imagePath)) {
    throw "Browser did not create the screenshot: $imagePath"
}
Get-Item -LiteralPath $imagePath | Select-Object Name,Length
