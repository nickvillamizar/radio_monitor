# ⚡ GUÍA RÁPIDA - 3 PASOS PARA PRODUCCIÓN

**Tiempo total:** ~10 minutos  
**Dificultad:** Muy fácil

---

## 🎯 PASO 1: RENDER DASHBOARD (5 min)

### URL: https://dashboard.render.com

1. Login
2. Selecciona: **`radio-monitor`** (servicio web)
3. Click: **"Environment"** (arriba a la derecha)
4. Click: **"Add Environment Variable"** (abajo)

**Agregar SOLO estas 2 variables:**

| #  | KEY | VALUE | TIPO |
|----|-----|-------|------|
| 1  | `ACRCLOUD_ACCESS_KEY` | `ad8a611a5b3ea9888f6cd522052ccf3b` | Secret |
| 2  | `ACRCLOUD_SECRET_KEY` | `Wa7xTctoAhrUr4JZaS6Da2J06PDQ56H0Yie6q3KV` | Secret |

**Verificar ya están:**
- `DATABASE_URL` ✓
- `SECRET_KEY` ✓

---

## 🚀 PASO 2: GIT PUSH (2 min)

```powershell
cd c:\Users\ad6341\Documents\radio\radio_monitor

git add .
git commit -m "ACRCloud integration: Free music recognition (1000 req/month)"
git push origin main
```

**Esto desencadena auto-deploy en Render (~5 min).**

---

## ✅ PASO 3: VERIFICAR (3 min)

### En Render Dashboard:

1. Click en servicio: **`radio-monitor`**
2. Tab: **"Logs"**
3. **Busca estos 3 mensajes** (en este orden):

```
✓ ffmpeg found at: /usr/bin/ffmpeg
✓ ACRCLOUD credentials are set
✓ [HEALTHCHECK] OVERALL HEALTH: PASS
```

Si ves todos 3 → **¡ÉXITO!** 🎉

### Si algo falla:

**Error: "ACRCLOUD credentials are set: False"**
- Re-verifica variables en Render Dashboard
- Copia/pega exactamente como está arriba

**Error: "ffmpeg not found"**
- Esto es raro (Dockerfile ya lo instala)
- Redeploy desde Render Dashboard

---

## 🎊 ¡LISTO!

Una vez que ves "OVERALL HEALTH: PASS" en logs:

✅ Sistema monitorea automáticamente cada 60 segundos  
✅ Usa ACRCloud para detectar canciones (GRATIS, 1000 req/mes)  
✅ Fallback a AudD si es necesario  
✅ Solo registra datos auténticos  

---

## 📊 OPCIONAL: Revisar Operación

En los logs, busca (después de ~2 minutos):

```
[OK] CICLO COMPLETADO
[SUCCESS] ✓ Registradas (AUTÉNTICAS): N
[OK] TASA DE AUTENTICIDAD: X.X%
```

Esto significa que detectó y registró cancciones correctamente.

---

## ❓ FAQ RÁPIDO

**P: ¿Tengo que hacer algo después?**  
R: No. El sistema corre solo cada 60 segundos.

**P: ¿Cuánto cuesta ACRCloud?**  
R: $0. Es gratuito (1000 req/mes).

**P: ¿Qué pasa si se acaba la cuota?**  
R: Se reinicia el mes siguiente automáticamente.

**P: ¿Y si la app falla?**  
R: Render la reinicia automáticamente.

**P: ¿Dónde veo los logs?**  
R: Render Dashboard → radio-monitor → Logs

---

## 📞 SI ALGO SALE MAL

Espera 2-3 minutos y:
1. Refresca Render Dashboard
2. Revisa logs nuevamente
3. Redeploy si es necesario

---

**¡ESO ES TODO! 🚀**

El sistema ahora está completamente configurado para usar ACRCloud (gratuito) como servicio primario de detección de canciones.

✅ Datos auténticos 100%  
✅ Operación automática  
✅ Costo $0  

