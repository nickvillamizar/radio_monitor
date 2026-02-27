# 🚀 CONFIGURAR RENDER PARA ACRCLOUD

**Tiempo estimado:** 10 minutos  
**Dificultad:** Muy fácil

---

## 📍 Acceder a Render Dashboard

1. Ve a: https://dashboard.render.com
2. Login con tu cuenta
3. Selecciona servicio: **`radio-monitor`**
4. Click en: **"Environment"**

---

## 📝 VARIABLES A CONFIGURAR

### 🔹 ACRCloud (PRIMARIO - NUEVO)

| Campo | Valor | Tipo |
|-------|-------|------|
| **Key** | `ACRCLOUD_ACCESS_KEY` | Secret |
| **Value** | `ad8a611a5b3ea9888f6cd522052ccf3b` | |

**Pasos:**
1. Click "Add Environment Variable"
2. Key: `ACRCLOUD_ACCESS_KEY`
3. Value: `ad8a611a5b3ea9888f6cd522052ccf3b`
4. Seleccionar tipo: "Secret" (encriptado)
5. Click "Save"

---

### 🔹 ACRCloud Secret (NUEVO)

| Campo | Valor | Tipo |
|-------|-------|------|
| **Key** | `ACRCLOUD_SECRET_KEY` | Secret |
| **Value** | `Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV` | |

**Pasos:**
1. Click "Add Environment Variable"
2. Key: `ACRCLOUD_SECRET_KEY`
3. Value: `Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV`
4. Seleccionar tipo: "Secret" (encriptado)
5. Click "Save"

---

### 🔹 DATABASE_URL (MANTENER)

| Campo | Valor | Tipo |
|-------|-------|------|
| **Key** | `DATABASE_URL` | Secret |
| **Value** | `postgresql://neondb_owner:npg_...@ep-rough-leaf-adci1see...` | |

**Nota:** Ya debería estar configurada. Si no:
1. Copiar URL desde Neon: https://console.neon.tech
2. Pegar en Render Dashboard

---

### 🔹 SECRET_KEY (MANTENER)

| Campo | Valor | Tipo |
|-------|-------|------|
| **Key** | `SECRET_KEY` | Secret |
| **Value** | (tu clave actual) | |

**Nota:** Ya debería estar configurada.

---

### 🔹 AUDD_API_TOKEN (OPCIONAL)

| Campo | Valor | Tipo |
|-------|-------|------|
| **Key** | `AUDD_API_TOKEN` | Secret |
| **Value** | (solo si tienes token válido) | |

**Nota:** OPCIONAL. Solo si AudD es fallback.

---

### 🔹 CONFIG DE APP (YA CONFIGURADO)

```
MONITOR_INTERVAL = 60
FLASK_ENV = production
WORKERS = 2
```

---

## ✅ VERIFICAR CONFIGURACIÓN

Después de guardar todas las variables:

```
ACRCLOUD_ACCESS_KEY ✓
ACRCLOUD_SECRET_KEY ✓
DATABASE_URL ✓
SECRET_KEY ✓
MONITOR_INTERVAL ✓
FLASK_ENV ✓
WORKERS ✓
```

---

## 🚀 DESPLEGAR

### Opción A: Auto-Deploy (RECOMENDADO)

1. Ve a GitHub: https://github.com/[tu-repo]/radio_monitor
2. Haz commit + push:
   ```bash
   git add .
   git commit -m "ACRCloud integration: Free music recognition"
   git push origin main
   ```
3. Render automáticamente detectará cambios y desplegará (~5 min)

### Opción B: Manual Deploy

1. En Render Dashboard
2. Click "Deploy" (botón arriba a la derecha)
3. Selecciona rama: `main`
4. Click "Create Deploy"

---

## 📊 VERIFICAR DESPLIEGUE

### Paso 1: Ver Logs
En Render Dashboard:
1. Click en servicio: `radio-monitor`
2. Tab: "Logs"
3. Busca estos mensajes (en orden):

```
✓ ffmpeg found at: /usr/bin/ffmpeg
✓ ACRCLOUD credentials are set
✓ OVERALL HEALTH: PASS
[OK] SISTEMA PERIODÍSTICO PROFESIONAL - INICIANDO
[RADIO] 10 emisoras a procesar
```

### Paso 2: Verificar App Activa
```bash
curl https://radio-monitor-xxxx.onrender.com/
# Debe devolver HTML (dashboard)
```

### Paso 3: Revisar Primer Ciclo
En logs, busca:
```
[SUCCESS] ✓ Registradas (AUTÉNTICAS): N
[OK] TASA DE AUTENTICIDAD: X.X%
```

---

## ⏱️ TIMELINE ESPERADO

| Fase | Tiempo | Estado |
|------|--------|--------|
| Git push | 1 min | ✅ |
| Render detecta cambios | 1 min | 🔄 |
| Build Docker | 2-3 min | 🔄 |
| Healthcheck | 1 min | 🔄 |
| App inicia monitor | 1 min | 🔄 |
| Primer ciclo completa | 2 min | 🔄 |
| **Total** | **~8-10 min** | **✅** |

---

## 🎯 CONFIRMACIÓN FINAL

Cuando veas en logs:

```
[OK] CICLO COMPLETADO - REPORTE FINAL (SOLO DATOS AUTÉNTICOS)
[SUCCESS] ✓ Registradas (AUTÉNTICAS): N
[OK] TASA DE AUTENTICIDAD: X.X%
```

**¡Significa que está funcionando correctamente!**

---

## ⚠️ SI ALGO FALLA

### Error: `ACRCloud: False`
- Verificar variables en Render Dashboard
- Copiar/pegar credenciales exactamente
- Redeploy

### Error: `ffmpeg not found`
- Verificar Dockerfile contiene: `apt-get install -y ffmpeg`
- Redeploy

### Error: `DATABASE_URL NOT set`
- Obtener URL desde: https://console.neon.tech
- Pegar en Render Dashboard
- Redeploy

### Error: ConnectionError a ACRCloud
- Verificar internet en Render (normalmente está OK)
- Esperar 30 segundos + retry automático
- Si persiste: contactar soporte ACRCloud

---

## 📞 SOPORTE

**Render:** https://render.com/support  
**ACRCloud:** https://www.acrcloud.com/dashboard → Support  
**GitHub:** https://github.com/[tu-repo]/issues

---

**Una vez configuradas las variables, ¡no necesitas hacer nada más!**  
**El sistema monitorea automáticamente cada 60 segundos.**

✅ **LISTO PARA PRODUCCIÓN**
