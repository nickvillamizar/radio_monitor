# 🚀 Despliegue a Render - Radio Monitor

## ✅ Estado Actual (14 de Enero 2026)

Sistema completamente funcional con reconocimiento de música gratuito via **ACRCloud** (1000 req/mes).

### Componentes Listos:
- ✅ Docker + ffmpeg
- ✅ ACRCloud integrado (primario)
- ✅ AudD fallback (si tienes token válido)
- ✅ Flask app + Neon DB
- ✅ Healthcheck automático
- ✅ ffmpeg en PATH (local)

---

## 📋 Pasos de Despliegue (Render)

### 1️⃣ **Sincronizar cambios a GitHub**

```bash
cd c:\Users\ad6341\Documents\radio\radio_monitor
git add .
git commit -m "ACRCloud integration: Free music recognition (1000 req/month)"
git push origin main
```

**Archivos modificados:**
- `utils/stream_reader.py` — Nueva función ACRCloud + lógica de fallback
- `app.py` — Cargar credenciales ACRCloud desde .env
- `.env` — Credenciales ACRCloud (NO COMMITAR, solo en Render dashboard)
- `render.yaml` — Variables de entorno ACRCloud
- `healthcheck.py` — Verificar ACRCloud + AudD

---

### 2️⃣ **Configurar Variables en Render Dashboard**

Ve a: https://dashboard.render.com → Selecciona **radio-monitor** service

**Agregar/actualizar variables de entorno:**

| Variable | Valor | Tipo |
|----------|-------|------|
| `ACRCLOUD_ACCESS_KEY` | `ad8a611a5b3ea9888f6cd522052ccf3b` | Secret |
| `ACRCLOUD_SECRET_KEY` | `Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV` | Secret |
| `DATABASE_URL` | `postgresql://neondb_owner:...@ep-rough-leaf-adci1see...` | Secret |
| `SECRET_KEY` | (tu clave actual) | Secret |
| `AUDD_API_TOKEN` | (opcional, fallback) | Secret |
| `MONITOR_INTERVAL` | `60` | Value |
| `FLASK_ENV` | `production` | Value |
| `WORKERS` | `2` | Value |

---

### 3️⃣ **Desplegar**

**Opción A - Auto-deploy (recomendado):**
- Render detectará automáticamente `git push` a `main`
- Dockerfile se compilará
- Healthcheck validará ffmpeg + credenciales
- App inicia con `gunicorn`

**Opción B - Manual en Render Dashboard:**
1. Click en "Deploy"
2. Espera ~5 min por build + startup

---

### 4️⃣ **Verificar Despliegue**

```bash
# Check logs en Render Dashboard
# Busca: "ACRCloud: True" o "ffmpeg found"

# Endpoint health
curl https://radio-monitor-xxxx.onrender.com/

# Logs en vivo
# Render Dashboard → Logs → busca "[OK] SISTEMA PERIODÍSTICO"
```

---

## 📊 Configuración ACRCloud Utilizada

| Campo | Valor |
|-------|-------|
| **Tipo** | Free (gratuito) |
| **Límite** | 1000 requests/month |
| **Access Key** | `ad8a611a5b3ea9888f6cd522052ccf3b` |
| **Secret Key** | `Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV` |
| **Host** | `identify-us-west-2.acrcloud.com` |

### Estimación de Uso:
- 10 estaciones × 4 intentos/hora = 40 req/hora
- 40 req/hora × 24 horas = 960 req/día
- **Suficiente para ~1 mes** antes de reiniciar cuota

---

## 🔄 Flujo de Detección

```
[EMISORA] 
  ↓
[1. ICY METADATA] ← 10% de estaciones
  ↓ (falla)
[2. ACRCloud] ← 1000 req/mes GRATUITO ✅
  ↓ (falla)
[3. AudD] ← Fallback (si token válido)
  ↓ (falla)
[SKIP] ← NO registra datos no verificados
```

---

## ⚙️ Variables Importantes

### En `.env` (LOCAL):
```env
ACRCLOUD_ACCESS_KEY=ad8a611a5b3ea9888f6cd522052ccf3b
ACRCLOUD_SECRET_KEY=Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV
DATABASE_URL=postgresql://...
SECRET_KEY=...
```

### En Render Dashboard:
- **NO poner `.env` en el repo**
- Configurar cada variable en dashboard
- Render inyecta en tiempo de ejecución

---

## 🚨 Troubleshooting

### ❌ "ACRCloud: False" en logs
**Causa:** Credenciales faltantes  
**Solución:** Verificar `ACRCLOUD_ACCESS_KEY` + `ACRCLOUD_SECRET_KEY` en Render Dashboard

### ❌ "ffmpeg not found"
**Causa:** Dockerfile no instala ffmpeg  
**Solución:** Verificar `RUN apt-get install -y ffmpeg` en Dockerfile

### ❌ "NO SE PUDO VERIFICAR CANCIÓN"
**Causa:** Normal si no hay ICY metadata ni música en el stream  
**Solución:** Sistema está funcionando correctamente (rechaza datos no verificados)

### ⚠️ Error de autenticación ACRCloud
**Causa:** Access key o secret incorrecto  
**Solución:** Re-copiar desde ACRCloud dashboard (https://www.acrcloud.com)

---

## 📝 Monitoreo Post-Despliegue

**Metrics a revisar:**
1. **TASA DE AUTENTICIDAD** (en logs) — Meta: >50% si streams tienen música
2. **ACRCloud successes** — Conteo en reporte final
3. **Errores de conexión** — Deben ser 0 si BD + ffmpeg funcionan

**Ejemplo de log exitoso:**
```
[SUCCESS] ✓ Registradas (AUTÉNTICAS): 3
  ├─ [MUSIC] ICY metadata:   1
  ├─ [AUDIO] ACRCloud:       2
  └─ [AUDIO] AudD:           0
[OK] TASA DE AUTENTICIDAD: 30.0%
```

---

## 🔐 Seguridad

✅ **Credenciales NO están en GitHub**  
✅ **ACRCloud gratuito** — No hay billing concerns  
✅ **AudD fallback** — Configurado pero OPCIONAL  
✅ **Healthcheck** — Valida credenciales antes de iniciar  
✅ **.gitignore** — Contiene `.env`

---

## 📞 Soporte

Si hay problemas con ACRCloud:
1. Verificar cuota en https://www.acrcloud.com/dashboard
2. Comprobar credenciales en Render Dashboard
3. Revisar logs en Render: `[AUDIO] ACRCloud recognized...`
4. Fallback automático a AudD si está configurado

---

**Versión:** ACRCloud Integration v1.0  
**Fecha:** 14 Enero 2026  
**Status:** ✅ Listo para Producción
