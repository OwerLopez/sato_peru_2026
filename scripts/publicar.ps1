# Publica el sistema completo en una URL publica temporal (tunel de Cloudflare) e imprime la direccion.
# Requisitos: Docker Desktop en ejecucion y la base de datos ya cargada.
#   powershell -ExecutionPolicy Bypass -File scripts/publicar.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$archivos = @("-f", "docker-compose.yml", "-f", "deploy/docker-compose.tunel.yml")
docker compose @archivos up -d --build db api web tunel | Out-Null
Write-Host "Esperando la URL publica del tunel..."
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep -Seconds 2
    $log = docker compose @archivos logs tunel 2>&1 | Out-String
    $m = [regex]::Matches($log, "https://[a-z0-9-]+\.trycloudflare\.com")
    if ($m.Count -gt 0) { $url = $m[$m.Count - 1].Value }
}
if (-not $url) { throw "No se obtuvo la URL del tunel. Revise: docker compose $($archivos -join ' ') logs tunel" }
for ($i = 0; $i -lt 30; $i++) {
    try { if ((Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 10).StatusCode -eq 200) { break } } catch { Start-Sleep -Seconds 2 }
}
Write-Host ""
Write-Host "Sistema publicado en: $url"
Write-Host "La URL cambia si se reinicia el tunel o el equipo. Mantenga el equipo encendido y sin suspension."
