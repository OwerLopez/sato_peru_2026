# Instala y levanta SATO en otro equipo a partir de un respaldo de la base de datos (sin descargar ni reprocesar
# las fuentes, que toma horas). Requisitos: Docker Desktop en ejecucion, el archivo .env copiado en la raiz del
# repositorio y el respaldo .dump generado con scripts/backup_db.sh.
#   powershell -ExecutionPolicy Bypass -File scripts/instalar_laptop.ps1 -Respaldo D:\sato_AAAAMMDD_HHMMSS.dump
#   agregar -Publicar para obtener ademas una URL publica temporal (tunel de Cloudflare)
# Si la base ya tiene datos, no se vuelve a restaurar: el script solo levanta los servicios.
param(
    [string]$Respaldo,
    [switch]$Publicar
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Paso($t) { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }

Paso "Verificando Docker y configuracion"
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop no esta en ejecucion. Abralo, espere a que diga 'Engine running' y vuelva a ejecutar." }
if (-not (Test-Path ".env")) { throw "Falta el archivo .env en $(Get-Location). Copie el .env del equipo original (contiene las claves)." }
$puerto = if ($env:WEB_PORT) { $env:WEB_PORT } else { ((Get-Content .env | Where-Object { $_ -match '^WEB_PORT=' }) -replace 'WEB_PORT=', '') }
if (-not $puerto) { $puerto = "8080" }

Paso "Levantando la base de datos"
docker compose up -d db
if ($LASTEXITCODE -ne 0) { throw "No se pudo levantar la base de datos." }
for ($i = 0; $i -lt 60; $i++) {
    docker compose exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 2
}
# la consulta va por la entrada estandar: PowerShell 5 elimina las comillas dobles de los argumentos a programas externos
function Contar-Obras { ("select count(*) from sato.obra;" | docker compose exec -T db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -At 2>/dev/null' | Out-String).Trim() }
$obras = Contar-Obras
if ($obras -notmatch '^\d+$' -or [int]$obras -eq 0) {
    if (-not $Respaldo -or -not (Test-Path $Respaldo)) { throw "La base esta vacia. Indique el respaldo con -Respaldo <ruta al archivo .dump>." }
    Paso "Restaurando el respaldo (puede tardar entre 10 y 30 minutos)"
    docker compose cp "$Respaldo" db:/tmp/sato.dump
    if ($LASTEXITCODE -ne 0) { throw "No se pudo copiar el respaldo al contenedor." }
    docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner -j 4 /tmp/sato.dump'
    $codigo = $LASTEXITCODE
    docker compose exec -T db rm -f /tmp/sato.dump
    if ($codigo -ne 0) { throw "pg_restore termino con errores (codigo $codigo)." }
    $obras = Contar-Obras
    Write-Host "Base restaurada: $obras obras."
} else {
    Write-Host "La base ya tiene datos ($obras obras): no se restaura."
}

Paso "Construyendo y levantando la API y la web (la primera vez descarga dependencias)"
docker compose up -d --build api web
if ($LASTEXITCODE -ne 0) { throw "No se pudieron levantar la API y la web." }
$url = "http://127.0.0.1:$puerto"
$ok = $false
for ($i = 0; $i -lt 90 -and -not $ok; $i++) {
    try { $ok = (Invoke-WebRequest "$url/api/ready" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { Start-Sleep -Seconds 2 }
}
if (-not $ok) { throw "La API no respondio en $url/api/ready. Revise: docker compose logs api" }
Write-Host ""
Write-Host "SATO esta funcionando en: $url" -ForegroundColor Green

if ($Publicar) {
    Paso "Publicando en una URL temporal"
    & (Join-Path $PSScriptRoot "publicar.ps1")
}
