# Despliegue y operación

## 1. Local (verificado)

```bash
cp .env.example .env                       # reemplazar todas las claves (python -c "import secrets;print(secrets.token_urlsafe(48))")
docker compose up -d --build db api web
docker compose --profile carga run --rm cargador
```

* Web: <http://localhost:8080> · API: <http://localhost:8080/api/v1> · OpenAPI: <http://localhost:8080/api/docs>
* Salud: `curl http://localhost:8080/api/ready` → `{"status":"ready","modelo":"atraso-H60-B_full-…","corte_datos":"…"}`
* Estado operativo: `curl http://localhost:8080/api/v1/sistema/estado` (o la pantalla «Estado y monitoreo»).
* La base de datos escucha solo en `127.0.0.1:5432` y la web en `127.0.0.1:8080`. Para mostrarla en la red local se define
  `WEB_BIND=0.0.0.0` y `WEB_BIND6=[::]` en `.env` (sin HTTPS: solo en redes de confianza).

## 2. Público con dominio propio (VM + Docker + HTTPS automático)

**Lo que debe hacer el equipo (requiere cuentas o pagos que no se automatizan desde aquí):**

1. Contratar una VM Linux (2 vCPU, 4 GB de RAM y 30 GB de disco; la base nacional ocupa unos 6,4 GB).
2. Registrar un dominio (o subdominio institucional) y crear un registro DNS `A` hacia la IP de la VM.
3. Abrir solo los puertos 80 y 443 en el firewall del proveedor.

**Luego, en la VM:**

```bash
git clone <repositorio> sato && cd sato
cp .env.example .env && nano .env         # secretos fuertes; SATO_CORS_ORIGINS=https://<dominio>; SATO_BASE_URL=https://<dominio>
# Copiar los artefactos generados por el pipeline (los datos pesados no se versionan):
#   rsync -a data/curated data/staging data/features data/raw/manifest.jsonl artifacts/ usuario@vm:sato/...
DOMAIN=<dominio> docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
docker compose --profile carga run --rm cargador
docker compose --profile worker up -d worker   # sincronización mensual automática y resumen semanal
```

Caddy obtiene y renueva el certificado TLS (Let's Encrypt) y añade HSTS. En esta superposición la web no publica puertos:
todo el tráfico entra por Caddy.

## 3. Operación

| Tarea | Cómo | Frecuencia |
|---|---|---|
| Actualización de datos | Automática con el worker (día `SATO_SYNC_DIA`), o manual: `python -m sato.pipeline all` en el equipo con GPU, copiar `data/` y `artifacts/`, correr el `cargador` | Mensual |
| Revisar el resultado de una carga | Pantalla «Estado y monitoreo» → «Actualizaciones de datos» (compuerta y conciliación), o `/api/v1/sistema/cargas` | Tras cada carga |
| Carga rechazada por caída de filas | Revisar la fuente; si la caída es real y está justificada, repetir con `SATO_CARGA_FORZAR=1` (queda registrado) | Excepcional |
| Deriva del modelo (PSI > 0,25) | Contrastar con el desempeño realizado; si se sostiene, reentrenar (`experiments`, `release`) y repetir la validación temporal | Según aviso |
| Respaldo | `0 3 * * * cd /ruta/sato && ./scripts/backup_db.sh /ruta/backups` | Diario |
| Avisos | Definir `SATO_ALERTAS_EMAIL` y SMTP (`SATO_SMTP_*`); sin SMTP los avisos quedan en `artifacts/outbox` | Continuo |
| Errores completos de sincronización | `/api/v1/admin/sincronizaciones` (rol admin) | Según aviso |

**Recuperación.** Una carga fallida o rechazada no modifica la base (transacción única). Si el proceso se interrumpe, la
siguiente sincronización marca la anterior como interrumpida y vuelve a intentar. El respaldo es de la base completa
(esquema, extensiones, configuración de búsqueda y registro de migraciones) y se restaura en una base nueva:
`docker compose exec -T db createdb -U sato sato_restaurada` y
`docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d sato_restaurada --no-owner' < sato_AAAAMMDD_HHMMSS.dump`;
luego se apunta `POSTGRES_DB` a la base restaurada. Toda la base, salvo usuarios, revisiones,
suscripciones y auditoría, se puede reconstruir desde el pipeline.

**Disponibilidad durante la carga.** La carga borra y reinserta dentro de una transacción con `DELETE` (no `TRUNCATE`): la API
sigue respondiendo con los datos vigentes hasta el `COMMIT`. La medición de una recarga completa está en
`artifacts/disponibilidad_durante_carga.json`.

## 4. Alternativa gestionada

* Frontend estático (`web/dist`) en un CDN con reglas de proxy de `/api` al servicio de la API (mismo origen).
* API: la imagen `docker/api.Dockerfile` corre en cualquier servicio de contenedores (`SATO_DATABASE_URL`, `SATO_JWT_SECRET`,
  `SATO_ENV=prod`, `SATO_CORS_ORIGINS`, `SATO_BASE_URL`).
* PostgreSQL 16 gestionado con respaldos automáticos; cargar con `DATABASE_URL=… python -m sato.pipeline load`.

## 5. URL pública temporal (demostraciones)

Un túnel efímero (por ejemplo, `cloudflared tunnel --url http://localhost:8080`) publica la instancia local mientras el equipo
esté encendido. Implica descargar el binario oficial del proveedor y exponer el equipo a Internet: debe hacerlo o autorizarlo
expresamente el equipo. No reemplaza un despliegue.

## Publicación temporal sin servidor (túnel de Cloudflare)

Para una demostración sin servidor propio, `deploy/docker-compose.tunel.yml` añade un túnel de Cloudflare
(`cloudflared`, sin cuenta ni puertos abiertos en el router) que publica la web con HTTPS en una URL
`*.trycloudflare.com`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publicar.ps1
```

El script levanta `db`, `api`, `web` y `tunel`, espera a que el túnel entregue su URL y verifica `/api/health`.
nginx confía en `X-Forwarded-For` solo cuando la conexión viene del contenedor del túnel (IP fija 172.31.0.10),
de modo que los límites de tasa se aplican por visitante. Limitaciones: la URL cambia cada vez que se reinicia el
túnel o el equipo, y el sistema deja de responder si el equipo anfitrión se apaga o entra en suspensión. Para una URL
estable se usa `deploy/docker-compose.prod.yml` en un servidor con dominio propio.

## Copia pública permanente en GitHub Pages (solo lectura)

https://owerlopez.github.io/sato_peru_2026/ publica, sin servidor, la interfaz con las respuestas reales de la API
del corte vigente. `scripts/exportar_estatico.py` recorre la interfaz con un navegador contra una API local sin
límite de tasa, registra cada consulta GET y guarda su respuesta como JSON (más el informe PDF de cada ficha); la
interfaz compilada con `VITE_ESTATICO=1` lee esos archivos con la misma clave (`web/src/estatico.ts`, verificada
por `web/src/estatico.test.ts`). El resultado se publica en la rama `gh-pages`.

```bash
# API local sin límite de tasa y la interfaz normal con proxy a esa API
SATO_RATE_LIMIT=100000/minute python -m uvicorn sato.api.main:app --port 8000 --workers 4
cd web && npx vite build --outDir dist-crawl && VITE_API_PROXY=http://127.0.0.1:8000 npx vite preview --outDir dist-crawl --port 4173
# interfaz estática y exportación de datos
VITE_ESTATICO=1 npx vite build --base /sato_peru_2026/ --outDir dist-pages
python scripts/exportar_estatico.py --web http://127.0.0.1:4173 --salida web/dist-pages/datos
cp web/dist-pages/index.html web/dist-pages/404.html && touch web/dist-pages/.nojekyll
# publicar el contenido de web/dist-pages en la rama gh-pages
```

Alcance: todas las pantallas para todo el Perú y los 25 departamentos, las fichas de las obras en riesgo alto y
las 60 primeras en riesgo medio del cuaderno digital, y las 100 primeras de la cartera en riesgo alto. No incluye
búsqueda libre, ingreso de analistas, suscripciones ni combinaciones de filtros fuera del recorrido: la interfaz
lo indica con un mensaje en lugar de mostrar datos incompletos.
