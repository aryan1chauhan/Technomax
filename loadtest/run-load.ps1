param(
  [ValidateSet("baseline", "peak", "spike", "soak")]
  [string]$Profile = "baseline",
  [string]$ApiBase = "http://localhost:8000",
  [string]$WsBase = "",
  [int]$Seed = 424242
)

$ErrorActionPreference = "Stop"

if (-not $WsBase) {
  $WsBase = $ApiBase -replace "^http", "ws"
}

$env:PROFILE = $Profile
$env:API_BASE = $ApiBase
$env:WS_BASE = $WsBase
$env:SEED = "$Seed"

$resultsDir = "loadtest/results"
if (-not (Test-Path $resultsDir)) {
  New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
}

Write-Host "[1/4] Running k6 dispatch load ($Profile)..."
k6 run "loadtest/k6/dispatch-load.js" --out "json=loadtest/results/dispatch-$Profile-timeseries.json"

Write-Host "[2/4] Installing WS harness dependencies (if needed)..."
Push-Location "loadtest/ws"
npm install

Write-Host "[3/4] Running WS load harness ($Profile)..."
node "ws-track-load.mjs" --profile $Profile
Pop-Location

Write-Host "[4/4] Building go/no-go report..."
python "loadtest/report/build_go_no_go_report.py" --profile $Profile --dispatch-summary "loadtest/results/dispatch-$Profile-summary.json" --ws-summary "loadtest/results/ws-$Profile-summary.json" --out "loadtest/results/go-no-go-$Profile.md"

Write-Host "Done. See loadtest/results for artifacts."
