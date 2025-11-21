# 🔍 SISTEMA DE VALIDACIÓN Y DIAGNÓSTICO DE EMISORAS

## Problema Identificado

Se ha detectado que **18 emisoras** presentan muy pocas métricas de reproducción (0-2 plays):

1. Fiestahn Radio (2)
2. Jupiter Radiomix (1)
3. Radio Vibra (1)
4. Alex Sensation Radio (1)
5. Guadalupana FM - La emperatriz del Norte (1)
6. Estéreo Utopica (1)
7. Power 800 AM (1)
8. La Mega 97.9 (1)
9. Arellano Stereo 98.5 FM (1)
10. La Mega Star 95.1 FM (0)
11. Expreso 89.1 FM (0)
12. Radio CTC Moncion 89.5 FM (M89.5) (0)
13. Cañar Stereo 97.3 FM (0)
14. La Excitante (0)
15. Sabrosa 91.1 Fm (S91.1) (0)
16. Radio Amboy (0)
17. La Kalle Sajoma 96.3 FM SJM (0)
18. La Kalle de Santiago 96.3 Fm (SANTIAGO) (0)

**Causa probable:** URLs de streaming no válidas o inaccesibles.

---

## ✅ SOLUCIÓN IMPLEMENTADA

Se ha integrado un **Sistema de Validación de URLs de Streaming** que:

- ✔️ Verifica si cada URL es accesible (HTTP/HEAD)
- ✔️ Detecta si es realmente un servidor de streaming
- ✔️ Registra el estado en la base de datos
- ✔️ Genera reportes de diagnóstico
- ✔️ Identifica problemas específicos

---

## 🚀 CÓMO USAR

### Opción 1: Línea de Comandos (Recomendado)

#### 1️⃣ Listar emisoras problemáticas

```bash
flask get-failing-stations
```

Muestra todas las emisoras con 0-2 plays, ordenadas por importancia.

**Salida esperada:**
```
📻 EMISORAS CON POCAS MÉTRICAS (0-2 plays)
================================================================================
⚠️  Se encontraron 18 emisoras problemáticas:

1.  ❌ La Mega Star 95.1 FM (0 plays)
    URL: http://example.com/stream1
...
```

#### 2️⃣ Validar TODAS las emisoras

```bash
flask validate-streams
```

Conecta a cada URL y genera un reporte completo.

**Salida esperada:**
```
🔍 Iniciando validación de URLs de streaming...

📻 Validando 52 emisora(s)...

📊 RESUMEN
  - Total de emisoras: 52
  - URLs válidas: 45 (86%)
  - URLs alcanzables: 47 (90%)
  - Servidores streaming: 44 (84%)

================================================================================
ANÁLISIS POR EMISORA
================================================================================

📻 Radio Nacional
   URL: http://stream.national.com/live
   ✅ URL válida - Streaming activo
   Status: 200
   Tiempo respuesta: 125ms
   Content-Type: audio/mpeg

📻 La Mega Star 95.1 FM
   URL: http://invalid.url/stream
   ❌ No encontrado (404) - URL no válida
   Status: 404
   Tiempo respuesta: 230ms
   Error: HTTP_404
...

📄 Reporte guardado: C:\...\tmp\diagnostico_20250120_143022.txt
```

#### 3️⃣ Validar solo emisoras problemáticas

```bash
flask validate-streams --emisora-id 10
```

Valida una emisora específica con detalles.

#### 4️⃣ Modo verbose (detalles de cada intento)

```bash
flask validate-streams --verbose
```

Muestra cada intento de conexión:
```
[Intento 1/3] http://stream.url/live
    ✓ Conectado
    Status: 200
```

---

### Opción 2: Script Python Standalone

```bash
python validate_streams.py
```

Mismo que el comando CLI pero sin necesidad de variables de entorno.

**Opciones:**
```bash
python validate_streams.py --problematic   # Solo las problemáticas
python validate_streams.py --verbose       # Con detalles
```

---

### Opción 3: API HTTP

#### Validar una emisora específica

```bash
GET /api/validate/stream/<emisora_id>
```

**Ejemplo:**
```bash
curl http://localhost:5000/api/validate/stream/10
```

**Respuesta:**
```json
{
  "emisora_id": 10,
  "emisora_nombre": "La Mega Star 95.1 FM",
  "url": "http://stream.example.com/mega",
  "valid": false,
  "diagnosis": "❌ No encontrado (404) - URL no válida",
  "details": {
    "status_code": 404,
    "is_reachable": false,
    "is_streaming_server": false,
    "response_time_ms": 234.5,
    "content_type": "text/html",
    "error": "HTTP_404"
  }
}
```

#### Validar todas las emisoras

```bash
GET /api/validate/all-streams
GET /api/validate/all-streams?filter=problematic
```

**Respuesta:**
```json
{
  "total": 52,
  "validated": 52,
  "valid": 45,
  "invalid": 7,
  "problematic": [
    {
      "emisora_id": 10,
      "emisora_nombre": "La Mega Star 95.1 FM",
      "url": "http://...",
      "diagnosis": "❌ No encontrado (404)",
      "valid": false,
      "error": "HTTP_404"
    }
  ],
  "timestamp": "2025-01-20T14:30:22.123456"
}
```

#### Ver métricas de todas las emisoras

```bash
GET /api/stations/with-metrics
```

**Respuesta:**
```json
{
  "total": 52,
  "critical": 10,
  "warning": 8,
  "ok": 34,
  "stations": [
    {
      "id": 10,
      "nombre": "La Mega Star 95.1 FM",
      "url_stream": "http://...",
      "pais": "República Dominicana",
      "plays": 0,
      "url_valida": false,
      "es_stream_activo": false,
      "diagnostico": "❌ No encontrado (404)",
      "status": "critical"
    }
  ]
}
```

---

## 📊 DIAGNÓSTICOS POSIBLES

### ✅ URL Válida - Streaming Activo

```
Status: 200
Content-Type: audio/mpeg
Diagnóstico: ✅ URL válida - Streaming activo
```

**Acción:** No requiere cambios.

### ⚠️ URL Responde pero No es Streaming

```
Status: 200
Content-Type: text/html
Diagnóstico: ⚠️ URL responde pero no es streaming (Content-Type: text/html)
```

**Acciones sugeridas:**
- La URL puede ser un sitio web, no un servidor de streaming
- Buscar la URL correcta del streaming en el sitio web de la emisora
- Contactar a la emisora para obtener la URL correcta

### 🔐 Acceso Denegado

```
Status: 403
Diagnóstico: 🔐 Acceso denegado (403) - Requiere autenticación
```

**Acciones sugeridas:**
- La URL requiere credenciales (usuario/contraseña)
- Contactar al proveedor de streaming para obtener credenciales
- Verificar si hay una URL alternativa sin autenticación

### ❌ No Encontrado

```
Status: 404
Diagnóstico: ❌ No encontrado (404) - URL no válida
```

**Acciones sugeridas:**
- La URL no existe en el servidor
- Verificar que la URL sea correcta
- Contactar a la emisora para obtener la URL actual

### ⏱️ Timeout

```
Error: TIMEOUT
Diagnóstico: ⏱️ Timeout - Servidor no responde en tiempo límite
```

**Acciones sugeridas:**
- El servidor está lento o no responde
- Puede ser un problema temporal
- Intentar después de algunas horas
- Verificar si el servidor está en mantenimiento

### ❌ Error de Conexión

```
Error: CONNECTION_ERROR
Diagnóstico: ❌ Error de conexión - No se puede alcanzar el servidor
```

**Acciones sugeridas:**
- Verificar URL (sin typos, protocolo correcto)
- El servidor puede estar offline
- Problema de red o firewall
- Contactar al proveedor de hosting

---

## 🔧 CÓMO SOLUCIONAR

### 1. Para cada emisora problemática:

1. Ejecutar validación
2. Revisar el diagnóstico
3. Obtener la URL correcta
4. Actualizar en la base de datos

### 2. Formas de obtener URL correcta:

- **Sitio web de la emisora:** Buscar botón "Escuchar en vivo" o similar
- **Redes sociales:** Preguntar en Facebook/Twitter
- **Servicios de streaming:** TuneIn, Spotify (enlaces a streams)
- **Bases de datos de radio:** RadioBrowser, StreamGuide

### 3. Tipos de URLs válidas:

- `http://stream.example.com:port/path` - Stream directo
- `http://example.com/stream.m3u` - Playlist M3U
- `http://example.com/stream.pls` - Playlist PLS
- `http://shoutcast.example.com:8000/stream` - Shoutcast
- `http://icecast.example.com:8000/mount` - Icecast

---

## 📈 PRÓXIMOS PASOS

### Inmediato (Hoy)

1. ✅ Ejecutar `flask validate-streams` para obtener diagnóstico
2. ✅ Guardar reporte en `tmp/diagnostico_*.txt`
3. ✅ Revisar qué emisoras tienen URL incorrecta

### Corto Plazo (Esta semana)

1. Contactar a emisoras problemáticas
2. Obtener URLs correctas
3. Actualizar URLs en la base de datos
4. Re-validar

### Largo Plazo

1. Mantener validación automática semanal
2. Alertas cuando URL falla
3. Intentar auto-detectar nuevas URLs

---

## 📝 NOTAS TÉCNICAS

### Base de Datos

Se agregaron 4 columnas a la tabla `emisoras`:

```sql
- url_valida (BOOLEAN)           -- ¿URL accesible?
- es_stream_activo (BOOLEAN)     -- ¿Es servidor streaming?
- ultima_validacion (DATETIME)   -- Cuándo se validó
- diagnostico (VARCHAR 500)      -- Último diagnóstico
```

### Componentes Nuevos

- `utils/stream_validator.py` - Motor de validación
- `validate_streams.py` - Script standalone
- Comandos CLI en `app.py`
- Endpoints API en `app.py`

### Performance

- Timeout: 15 segundos por URL
- Reintentos: 3 intentos por URL
- Tiempo total: ~1-2 minutos por 50 emisoras

---

## 🆘 Contacto Soporte

Si necesita ayuda:

1. Ejecute: `flask get-failing-stations`
2. Copie el output
3. Ejecute: `flask validate-streams`
4. Adjunte el reporte de `tmp/diagnostico_*.txt`

---

**Versión:** 1.0  
**Fecha:** Enero 2025  
**Autor:** Sistema de Diagnóstico Radio Monitor
