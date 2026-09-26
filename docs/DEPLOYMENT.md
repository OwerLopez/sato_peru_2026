# Despliegue

## 1. Local (verificado)

```bash
cp .env.example .env                       # reemplazar todas las claves (python -c "import secrets;print(secrets.token_urlsafe(48))")
docker compose up -d --build db api web
docker compose --profile carga run --rm cargador
```

* Web: <http://localhost:8080> · API: <http://localhost:8080/api/v1> · OpenAPI: <http://localhost:8080/api/docs>
* Salud: `curl http://localhost:8080/api/ready` → `{"status":"ready","modelo":"atraso-H60-B_full-…"}`
* La base de datos solo escucha en `127.0.0.1:5432`.

## 2. Público con dominio propio (VM + Docker + HTTPS automático)

**Lo que debe hacer el equipo (requiere cuentas/pagos que no pueden automatizarse desde aquí):**

1. Contratar una VM Linux (1–2 vCPU, 2–4 GB RAM, 20 GB disco): p. ej. un proveedor con créditos académicos.
2. Registrar un dominio (o subdominio institucional) y crear un registro DNS `A` hacia la IP de la VM.
3. Abrir los puertos 80 y 443 en el firewall del proveedor.

**Luego, en la VM:**

```bash
git clone <repositorio> sato-aqp && cd sato-aqp
cp .env.example .env && nano .env         # secretos fuertes; SATO_CORS_ORIGINS=https://<dominio>
# Copiar los artefactos generados por el pipeline (no se versionan los datos pesados):
#   rsync -a data/curated data/staging data/features data/raw/manifest.jsonl artifacts/ usuario@vm:sato-aqp/...
DOMAIN=<dominio> docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build
docker compose --profile carga run --rm cargador
```

Caddy obtiene y renueva el certificado TLS (Let's Encrypt) automáticamente y añade HSTS.

**Respaldo diario (cron):** `0 3 * * * cd /ruta/sato-aqp && ./scripts/backup_db.sh /ruta/backups`

**Actualización mensual:** ejecutar `python -m sato.pipeline all` en el equipo con GPU (o `features`→`load` si no cambia el
modelo), copiar `data/` y `artifacts/` a la VM y correr el `cargador`. El reporte de drift queda en
`artifacts/monitoring/reporte.json`.

## 3. Alternativa gestionada

* Frontend estático (`web/dist`) en un CDN; la variable de API se sirve por el mismo dominio mediante reglas de proxy del proveedor.
* API: la imagen `docker/api.Dockerfile` corre en cualquier servicio de contenedores (variables `SATO_DATABASE_URL`,
  `SATO_JWT_SECRET`, `SATO_ENV=prod`, `SATO_CORS_ORIGINS`).
* PostgreSQL 16 gestionado con backups automáticos; cargar con `DATABASE_URL=… python -m sato.pipeline load`.

## 4. URL pública temporal sin cuenta (demostraciones)

Un túnel efímero (p. ej. *Cloudflare Quick Tunnel*: `cloudflared tunnel --url http://localhost:8080`) publica la instancia
local con una URL `https://*.trycloudflare.com` mientras el equipo esté encendido. Implica descargar el binario oficial de
Cloudflare y exponer el equipo local a Internet: debe hacerlo o autorizarlo expresamente el equipo. No reemplaza un despliegue.
