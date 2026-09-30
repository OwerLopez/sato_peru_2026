# Ejecutar SATO en otra computadora (laptop)

Procedimiento para levantar el sistema completo en otro equipo **sin descargar ni reprocesar las fuentes**
(eso toma horas): se clona el código y se restaura un respaldo de la base de datos ya cargada.

## Qué llevar (por USB o disco externo)

| Archivo | De dónde sale | Nota |
|---|---|---|
| `sato_AAAAMMDD_HHMMSS.dump` | `scripts/backup_db.sh` en el equipo original (carpeta `backups/`) | Unos 550 MB; en la prueba, restaurar y arrancar tomó 8 minutos |
| `.env` | raíz del repositorio en el equipo original | Contiene las claves: no se sube a GitHub ni se comparte |

## Requisitos de la laptop

- Windows 10/11 con **Docker Desktop** instalado y abierto ("Engine running"), **Git** y 8 GB de RAM o más.
- Unos **10 GB libres** en disco: base restaurada 6,4 GB, respaldo 0,55 GB e imágenes de Docker 0,85 GB, además de Docker Desktop.
- **Internet la primera vez**, para descargar las imágenes y dependencias. Conviene hacerlo en casa, no en la universidad.

## Pasos (una sola vez)

```powershell
git clone https://github.com/OwerLopez/sato_peru_2026.git
cd sato_peru_2026
copy D:\.env .env
powershell -ExecutionPolicy Bypass -File scripts/instalar_laptop.ps1 -Respaldo D:\sato_AAAAMMDD_HHMMSS.dump
```

(`D:\` es la unidad del USB: reemplazarla por la que corresponda.)

El script verifica Docker y el `.env`, levanta la base de datos, restaura el respaldo, construye la API y la web y
comprueba `/api/ready`. Al terminar muestra `SATO esta funcionando en: http://127.0.0.1:8080`.

## El día de la exposición

1. Abrir Docker Desktop y esperar a que diga "Engine running".
2. En la carpeta del repositorio: `docker compose up -d db api web`. O ejecutar de nuevo `scripts/instalar_laptop.ps1`, que detecta que la base ya tiene datos y solo levanta los servicios.
3. Abrir `http://localhost:8080`.
4. Opcional, para que otros lo abran desde su celular: `powershell -ExecutionPolicy Bypass -File scripts/publicar.ps1`, que imprime una URL pública temporal `*.trycloudflare.com`. Requiere internet en la laptop y deja de funcionar al apagarla.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| "Docker Desktop no esta en ejecucion" | Abrir Docker Desktop y esperar "Engine running". |
| "Falta el archivo .env" | Copiar el `.env` del equipo original a la raíz del repositorio. |
| El puerto 8080 o 5432 está ocupado | Agregar `WEB_PORT=8090` o `DB_PORT=5433` al `.env` y volver a ejecutar. |
| La página tarda en abrir la primera vez | Es normal: la primera consulta calienta la caché de la base. |
| Ingresar como analista | Usar el correo y la contraseña de administrador del `.env` del equipo original. |
