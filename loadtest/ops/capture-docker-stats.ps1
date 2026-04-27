param(
  [int]$DurationMinutes = 30,
  [int]$IntervalSeconds = 15,
  [string]$OutputPrefix = "loadtest/results/soak",
  [string]$PostgresContainer = ""
)

$ErrorActionPreference = "Continue"

$statsFile = "${OutputPrefix}-docker-stats.csv"
$pgFile = "${OutputPrefix}-pg-connections.csv"

$statsDir = Split-Path $statsFile -Parent
if (-not (Test-Path $statsDir)) {
  New-Item -ItemType Directory -Path $statsDir -Force | Out-Null
}

"timestamp,container,cpu,mem_usage,mem_percent,net_io,block_io,pids" | Out-File -FilePath $statsFile -Encoding utf8
"timestamp,container,active_connections" | Out-File -FilePath $pgFile -Encoding utf8

if (-not $PostgresContainer) {
  $PostgresContainer = (docker ps --format "{{.Names}}" | Select-String -Pattern "postgres|db" | Select-Object -First 1).ToString()
}

$iterations = [Math]::Ceiling(($DurationMinutes * 60) / $IntervalSeconds)

for ($i = 0; $i -lt $iterations; $i++) {
  $timestamp = (Get-Date).ToString("o")

  docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}" |
    ForEach-Object { "$timestamp,$_" } | Out-File -FilePath $statsFile -Append -Encoding utf8

  if ($PostgresContainer) {
    try {
      $connCount = docker exec $PostgresContainer sh -lc "psql -U postgres -t -c \"select count(*) from pg_stat_activity;\"" 2>$null
      $normalized = ($connCount | Out-String).Trim() -replace "\s+", ""
      if (-not $normalized) { $normalized = "NA" }
      "$timestamp,$PostgresContainer,$normalized" | Out-File -FilePath $pgFile -Append -Encoding utf8
    } catch {
      "$timestamp,$PostgresContainer,NA" | Out-File -FilePath $pgFile -Append -Encoding utf8
    }
  }

  if ($i -lt $iterations - 1) {
    Start-Sleep -Seconds $IntervalSeconds
  }
}

Write-Host "Saved docker stats to $statsFile"
Write-Host "Saved Postgres connection samples to $pgFile"
