# Despliegue en Render

La app usa **Selenium + Chromium** para la sincronización con el portal WhaleTV, por eso
se despliega con **Docker** (el runtime nativo de Python no trae navegador).

## Pasos

1. Sube el repo a GitHub (el `.env` NO se sube; está en `.gitignore`).
2. En Render: **New > Blueprint** y apunta al repo (usa `render.yaml`), o crea un
   **Web Service** con runtime **Docker**.
3. Configura las variables de entorno (en el dashboard, marcadas como `sync:false`):
   - `DATABASE_URL` → la *Internal Database URL* de tu Postgres de Render.
   - `WHALETV_PORTAL_EMAIL` y `WHALETV_PORTAL_PASSWORD`.
   - `SECRET_KEY` (se autogenera con el blueprint) y `DEBUG=false`.
4. Render construye el `Dockerfile`, corre `migrate` (preDeployCommand) y arranca gunicorn.
5. Crea el superusuario una vez (Shell del servicio):
   `python manage.py createsuperuser`

## Variables de entorno

| Variable | Ejemplo | Notas |
|---|---|---|
| `SECRET_KEY` | (autogenerado) | clave de Django |
| `DEBUG` | `false` | en producción siempre false |
| `DATABASE_URL` | `postgres://...` | Internal URL del Postgres de Render |
| `WHALETV_PORTAL_EMAIL` | `tech@kayvegroup.com` | login del portal |
| `WHALETV_PORTAL_PASSWORD` | `••••` | password del portal |
| `WHALETV_PORTAL_HEADLESS` | `true` | siempre true en servidor |
| `TIME_ZONE` | `America/Bogota` | para las fechas de vencimiento |
| `WEB_CONCURRENCY` | `2` | procesos gunicorn |

## Notas importantes

- **Memoria:** cada navegador headless consume ~250-400 MB. En instancias pequeñas usa
  pocos *workers* en "Sincronizar todo" (1-2). Para 1000 TVs conviene una instancia con
  buena RAM.
- `ALLOWED_HOSTS` se completa solo con `RENDER_EXTERNAL_HOSTNAME`. Puedes añadir más con
  la variable `ALLOWED_HOSTS` (separadas por coma).
- Estáticos servidos por **WhiteNoise** (no necesitas otro servidor).
