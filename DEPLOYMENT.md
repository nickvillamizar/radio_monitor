# DEPLOYMENT.md - Despliegue en Render (via GitHub)

## Flujo del Deployment

```
Local (git push) → GitHub (Public Repo) → Render (Docker + Auto-Deploy) → Hostinger (Reverse Proxy)
```

---

## Prerequisitos

- ✅ Dockerfile en root (instala ffmpeg automáticamente)
- ✅ render.yaml (configuración de Render)
- ✅ healthcheck.py (verifica ffmpeg + tokens)
- ✅ requirements.txt (dependencias actualizadas)
- ✅ utils/stream_reader.py (mejorado: circuito-breaker AudD, detección ffmpeg)
- ✅ .env con AUDD_API_TOKEN, SECRET_KEY, DATABASE_URL

---

## Paso 1: Preparar GitHub

### 1.1 Asegurar que `.env` NO está versionado
```bash
# Verificar .gitignore contiene .env
cat .gitignore | grep "\.env"
# Si no está, añadir:
echo ".env" >> .gitignore
git add .gitignore
```

### 1.2 Commitar cambios finales
```bash
git add Dockerfile render.yaml healthcheck.py requirements.txt utils/stream_reader.py
git commit -m "🚀 Preparar deployment en Render: ffmpeg + AudD + healthcheck"
git push origin main
```

---

## Paso 2: Conectar Render

### 2.1 En render.com
1. Ve a **Dashboard** → **New** → **Web Service**
2. Conecta tu repositorio GitHub (radio_monitor)
3. Selecciona rama `main`

### 2.2 Configuración de Build & Deploy
- **Build Command**: (vacío — usa Dockerfile)
- **Start Command**: (vacío — usa Dockerfile CMD)
- **Runtime**: Docker
- **Plan**: Standard (o superior si necesitas)

### 2.3 Variables de Entorno (MUY IMPORTANTE)
En **Environment** → añade manualmente:

```
DATABASE_URL = postgresql://neondb_owner:npg_KwHW...@ep-rough-leaf-adci1see-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

AUDD_API_TOKEN = af9487123bb9013135e6428b1cd456

SECRET_KEY = 8f3c2b9a6e4d1a0c9f7e3b2d6a1c4e8f5a9d0b7e6c1f3a4b2d9e8c7f6a5b4

FLASK_ENV = production

MONITOR_INTERVAL = 60
```

⚠️ **CRÍTICO**: NO pegues estos datos en GitHub. Solo en Render dashboard (encriptado).

### 2.4 Deploy
- Click **Deploy** o espera a que auto-deploy en next push.
- Monitorea logs en **Logs** tab.

---

## Paso 3: Validar en Render

### 3.1 Logs esperados
Deberías ver:
```
✓ ffmpeg found at: /usr/bin/ffmpeg
✓ AUDD_API_TOKEN is set: af948712...b9013
✓ DATABASE_URL is set
✓ SECRET_KEY is set
[OK] HEALTHCHECK: All systems operational
```

### 3.2 Acceder a la app
```
https://radio-monitor.onrender.com/
```

### 3.3 Monitor automático
- El monitor thread arranca y comienza a procesar emisoras cada 60s.
- Verifique logs: busque `[AUDIO] Fallback: Intentando reconocimiento por audio` → debería usar AudD ahora (ffmpeg disponible).

---

## Paso 4: Conexión a Hostinger

Si Hostinger requiere reverse proxy (e.g., nginx/Apache):

### 4.1 En Hostinger
```nginx
server {
    listen 80;
    server_name tu-dominio.com;
    
    location / {
        proxy_pass https://radio-monitor.onrender.com;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

O usa un CNAME en DNS apuntando a Render.

---

## Solución de Problemas

### AudD aún devuelve 0 éxitos
1. ✅ Verificar que `ffmpeg` aparece en logs (debería ver `✓ ffmpeg found...`).
2. ✅ Verificar token es válido:
   - Ve a https://audd.io/dashboard → apikeys
   - Confirma balance/quota disponible.
3. ✅ Si aún falla, revisar respuestas crudas en `tmp/audd_resp_*.json` (ver logs para ruta).

### Healthcheck fallando
- Check: `AUDD_API_TOKEN` está definido en Render env vars.
- Check: `DATABASE_URL` válida y accesible desde Render.
- Reinicia el servicio en Render.

### Monitor thread no ejecutándose
- Logs deberían mostrar `[OK] Monitor iniciado exitosamente`.
- Si no aparece, revisar stderr/stdout en Render logs.

---

## Monitoreo Continuo

### KPIs a revisar en Logs
```
[AUDIO] Éxitos AudD:  ← Debe ser > 0 (con ffmpeg + token válido)
[PREDICT] PREDICCIÓN: ← Fallback si AudD falla
[SAVE] GUARDANDO EN BD: ← Confirmación de guardado
[OK] TASA DE ÉXITO: ← Meta: 70-100%
```

### Alertas automáticas (recomendado)
- En Render: configurar **Notifications** → email si service fails.
- En DB (Neon): revisar query logs si hay conexión lenta.

---

## Rotación de Token AudD

Cada 30 días (o si sospechas leak):

1. Ve a https://audd.io/dashboard → apikeys
2. Generate nuevo token
3. En Render dashboard → Environment → actualiza `AUDD_API_TOKEN`
4. Render reinicia automáticamente
5. Verifica en logs: `✓ AUDD_API_TOKEN is set`

---

## Resumen de Cambios Realizados

| Archivo | Cambio |
|---------|--------|
| `Dockerfile` | ✅ Nuevo: instala ffmpeg + deps, healthcheck |
| `render.yaml` | ✅ Nuevo: configuración nativa Render |
| `healthcheck.py` | ✅ Nuevo: verifica ffmpeg, tokens, DB |
| `requirements.txt` | ✅ Actualizado: versiones específicas, sin psycopg2 |
| `utils/stream_reader.py` | ✅ Mejorado: ffmpeg detection, circuit-breaker AudD, logging |
| `utils/test_audd.py` | ✅ Nuevo: script de prueba local AudD |
| `.env` | ⚠️ NO commitear (ya está en .gitignore) |

---

## Links Útiles

- Render Docs: https://render.com/docs/docker
- AudD API: https://audd.io/dashboard
- Neon PostgreSQL: https://console.neon.tech

---

**Versión**: 1.0 | **Fecha**: 2026-01-14 | **Estado**: LISTO PARA PRODUCCIÓN
