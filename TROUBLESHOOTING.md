# 🔧 GUÍA DE TROUBLESHOOTING

## Problemas Comunes y Soluciones

### 1. Error: "HAS_VALIDATOR is not defined"

**Síntoma:**
```
NameError: name 'HAS_VALIDATOR' is not defined
```

**Causa:** El validador no se importó correctamente

**Solución:**
```bash
# Verificar que el archivo exista
ls utils/stream_validator.py

# Verificar dependencias
pip install requests

# Reiniciar la aplicación
# Si usa gunicorn:
pkill -f gunicorn
gunicorn app:app
```

---

### 2. Error: "ModuleNotFoundError: No module named 'utils.stream_validator'"

**Síntoma:**
```
ModuleNotFoundError: No module named 'utils.stream_validator'
```

**Causa:** El archivo no está en la ubicación correcta

**Solución:**
1. Verificar que existe: `utils/stream_validator.py`
2. Verificar que existe: `utils/__init__.py` (puede estar vacío)
3. Ejecutar desde el directorio raíz del proyecto

---

### 3. Comando "flask validate-streams" no existe

**Síntoma:**
```
Error: No such command: validate-streams
```

**Causa:** La app Flask no está reconociendo los comandos CLI

**Solución:**
```bash
# Asegurarse que está en el directorio correcto
cd /ruta/al/proyecto

# Verificar que las variables de entorno estén configuradas
set FLASK_APP=app.py
set FLASK_ENV=development

# Listar comandos disponibles
flask --help

# Verificar que los comandos aparezcan
```

---

### 4. Timeout en validación de URLs

**Síntoma:**
```
⏱️  Timeout - Servidor no responde en tiempo límite
```

**Causa:** 
- Servidor lento
- Problema de red
- URL incorrecta

**Solución:**
```bash
# Aumentar timeout (editar stream_validator.py):
CONNECT_TIMEOUT = 30  # Cambiar de 10 a 30
READ_TIMEOUT = 10     # Cambiar de 5 a 10

# O probar manualmente:
curl -I --connect-timeout 30 http://url.ejemplo.com

# Ver si es problema de red:
ping url.ejemplo.com
tracert url.ejemplo.com  # Windows
```

---

### 5. "Validador no disponible" en API

**Síntoma:**
```json
{"error": "Validador no disponible"}
```

**Causa:** HAS_VALIDATOR es False

**Solución:**
1. Verificar que `utils/stream_validator.py` existe
2. Verificar que `requests` está instalado
3. Revisar logs de la aplicación

---

### 6. Base de datos: "column 'url_valida' does not exist"

**Síntoma:**
```
OperationalError: column "url_valida" does not exist
```

**Causa:** Columnas no fueron agregadas a la base de datos

**Solución:**
```bash
# Opción 1: Ejecutar migración Python
python migrate_db.py

# Opción 2: Ejecutar migración manual SQL
# Ver: migrations/add_stream_validation_columns.sql

# Opción 3: Recrear base de datos (PELIGRO: perderá datos)
python -c "from app import app, db; app.app_context().push(); db.drop_all(); db.create_all()"
```

---

### 7. Error: "URL malformada"

**Síntoma:**
```
❌ URL malformada
```

**Causa:** URL sin protocolo (http:// o https://)

**Solución:**
- Asegurarse que todas las URLs comiencen con `http://` o `https://`
- Actualizar base de datos

---

### 8. Muchos timeouts (>50%)

**Síntoma:**
```
⏱️  Timeout en 30+ emisoras
```

**Causa:** 
- Problema de red general
- Firewall bloqueando salidas
- Servidor proxy requerido

**Solución:**
```bash
# Verificar conectividad:
curl -I http://google.com

# Verificar puertos abiertos:
# Abrir en navegador: http://radio.ejemplo.com (una de las URLs)

# Si usa proxy:
# Editar stream_validator.py para usar proxy:
PROXIES = {
    'http': 'http://proxy.example.com:8080',
    'https': 'http://proxy.example.com:8080'
}
```

---

### 9. Performance: Validación muy lenta

**Síntoma:**
```
Toma más de 5 minutos para 50 emisoras
```

**Causa:**
- Timeouts muy altos
- Red lenta
- Servidor saturado

**Solución:**
```bash
# Reducir timeouts (pero con cuidado):
CONNECT_TIMEOUT = 5   # Cambiar de 10
READ_TIMEOUT = 3      # Cambiar de 5
MAX_RETRIES = 1       # Cambiar de 3

# O validar en paralelo:
# Editar stream_validator.py para usar ThreadPoolExecutor
```

---

### 10. Error: "Can't connect to database"

**Síntoma:**
```
OperationalError: could not connect to server
```

**Causa:** Base de datos no está disponible

**Solución:**
```bash
# Verificar que DATABASE_URL está configurada:
echo $DATABASE_URL

# Si usa Neon:
# - Verificar que URL es correcta
# - Verificar que se puede alcanzar desde donde ejecuta

# Probar conexión:
psql $DATABASE_URL -c "SELECT 1"
```

---

### 11. Reporte no se guarda

**Síntoma:**
```
No se crea archivo en tmp/diagnostico_*.txt
```

**Causa:** Carpeta tmp no tiene permisos de escritura

**Solución:**
```bash
# Crear carpeta
mkdir -p tmp

# Dar permisos (Linux/Mac)
chmod 755 tmp

# O cambiar ruta en stream_validator.py
```

---

### 12. URL actualizada pero validación sigue siendo negativa

**Síntoma:**
```
Cambió URL, pero validación dice que sigue inválida
```

**Causa:** 
- Caché de conexión
- URL realmente inválida
- Problema temporal del servidor

**Solución:**
```bash
# Limpiar caché:
# Editar stream_validator.py
validator.results_cache.clear()

# Probar URL manualmente:
curl -I -v http://url.nueva/stream

# Esperar y reintentar después de 1 hora
```

---

### 13. ImportError: "No module named 'config'"

**Síntoma:**
```
ImportError: cannot import name 'Config' from 'config'
```

**Causa:** Directorio incorrecto o config.py falta

**Solución:**
```bash
# Verificar que config.py existe en raíz:
ls -la config.py

# Ejecutar desde directorio correcto:
cd /ruta/correcta
python validate_streams.py
```

---

### 14. Error: "Invalid email or password" (Neon)

**Síntoma:**
```
OperationalError: FATAL: invalid user "invalid_user"
```

**Causa:** DATABASE_URL tiene credenciales incorrectas

**Solución:**
1. Verificar credenciales en `.env`
2. Verificar que DATABASE_URL tiene formato correcto:
   ```
   postgresql://user:password@host:port/database?ssl=require
   ```
3. Probar con credenciales manuales

---

### 15. Validación se congela

**Síntoma:**
```
El proceso queda congelado sin terminar
```

**Causa:** 
- Socket stuck en conexión
- Timeout no configurado correctamente
- URL que causa infinite loop

**Solución:**
```bash
# Matar proceso:
Ctrl+C

# O desde otra terminal:
ps aux | grep validate_streams
kill -9 <PID>

# Ejecutar con timeout del SO:
timeout 300 flask validate-streams

# Editar para verificar limits
```

---

## 🔍 DIAGNÓSTICO AVANZADO

### Ver logs detallados

```bash
# Exportar logs
python validate_streams.py --verbose 2>&1 | tee diagnostico.log

# Ver línea exacta de error:
tail -f /var/log/app.log
```

### Probar URL manualmente

```bash
# Test simple
curl -I http://url.ejemplo.com

# Test con headers
curl -I -v http://url.ejemplo.com

# Test con User-Agent
curl -I -H "User-Agent: RadioMonitor/3.0" http://url.ejemplo.com

# Test con timeout
curl --connect-timeout 5 -I http://url.ejemplo.com
```

### Información de sistema

```bash
# Python
python --version
pip list | grep requests

# Red
ipconfig /all
netstat -an

# Disco
df -h

# Memoria
free -h  # Linux
tasklist  # Windows
```

---

## 📞 SOPORTE

Si el problema persiste:

1. **Recolectar información:**
   - Versión de Python: `python --version`
   - URL problemática
   - Error exacto (copy-paste completo)
   - Logs: `tmp/diagnostico_*.txt`

2. **Ejecutar test:**
   ```bash
   python test_validator.py
   python migrate_db.py
   ```

3. **Contactar soporte con:**
   - Información de sistema
   - Output del test
   - Reporte de diagnóstico

---

**Versión:** 1.0
**Actualizado:** Enero 2025
