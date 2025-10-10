"""
pstrace_connection.py

Módulo para obtener datos del potenciostato en tiempo real.
Si no hay dispositivo, reutiliza la carga desde un archivo .pssession.
"""

import os
import sys
import logging

# 1) Añadir ruta raíz del proyecto para importar pstrace_session
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2) Importar funciones de pstrace_session
try:
    from src.pstrace_session import (
        cargar_sesion_pssession,
        configurar_entorno_python_net,
        configurar_sdk_palmsens,
        extract_session_dict,
        cargar_limites_ppm
    )
    # Alias internos para consistencia en este módulo
    cargar_sesion = cargar_sesion_pssession
    extraer_generar = extract_session_dict
    cargar_limites = cargar_limites_ppm

    # Inyectar alias directamente en el módulo pstrace_session
    import sys
    import src.pstrace_session as _ps
    _ps.cargar_sesion = cargar_sesion_pssession
    _ps.extraer_generar = extract_session_dict
    _ps.cargar_limites = cargar_limites_ppm

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    log = logging.getLogger("pstrace_connection")
    log.info("✓ pstrace_session importado correctamente con alias de compatibilidad.")
except ImportError as e:
    import logging, sys
    logging.error("✗ Error al importar pstrace_session: %s", e)
    sys.exit(1)

# 3) Inicializar entorno .NET y SDK PalmSens
net_ok, Assembly, String, Boolean, clr = configurar_entorno_python_net()
if not net_ok:
    sys.exit(1)

dll_path = configurar_sdk_palmsens()
try:
    clr.AddReference(dll_path)
    log.info("✓ SDK PalmSens inicializado en pstrace_connection")
except Exception as e:
    log.error("✗ Error cargando referencia PalmSens: %s", e)
    sys.exit(1)

# ===================================================================================
# BLOQUE 2: DESCUBRIMIENTO DE DISPOSITIVOS
# ===================================================================================

from typing import List, Dict

def descubrir_instrumentos() -> List[Dict]:
    """
    Descubre instrumentos disponibles (USB, Bluetooth, TCP).
    Retorna lista de dicts uniformes:
    {
        'name': str,
        'serial': str|None,
        'transport': 'USB'|'Bluetooth'|'TCP',
        'address': 'COMx'|'BT:AA:BB:...'|'host:port'
    }
    """
    dispositivos = []
    try:
        import pspymethods

        # Ajusta a lo que realmente exponga tu SDK.
        usb_list = []
        bt_list = []
        tcp_list = []

        if hasattr(pspymethods, "list_usb_devices"):
            usb_list = pspymethods.list_usb_devices()
        if hasattr(pspymethods, "list_bluetooth_devices"):
            bt_list = pspymethods.list_bluetooth_devices()
        if hasattr(pspymethods, "list_tcp_endpoints"):
            tcp_list = pspymethods.list_tcp_endpoints()

        # Normalizar resultados
        for dev in usb_list:
            dispositivos.append({
                'name': getattr(dev, 'Name', 'PalmSens'),
                'serial': getattr(dev, 'SerialNumber', None),
                'transport': 'USB',
                'address': getattr(dev, 'PortName', None),  # ej: 'COM3'
            })
        for dev in bt_list:
            dispositivos.append({
                'name': getattr(dev, 'Name', 'PalmSens'),
                'serial': getattr(dev, 'SerialNumber', None),
                'transport': 'Bluetooth',
                'address': getattr(dev, 'Address', None),  # ej: 'BT:AA:BB:CC:DD:EE'
            })
        for dev in tcp_list:
            dispositivos.append({
                'name': getattr(dev, 'Name', 'PalmSens'),
                'serial': getattr(dev, 'SerialNumber', None),
                'transport': 'TCP',
                'address': getattr(dev, 'Endpoint', None),  # ej: '192.168.1.50:8080'
            })

        log.info(f"✓ Descubiertos {len(dispositivos)} dispositivos")
        return dispositivos

    except Exception as e:
        log.exception("✗ Error durante la descubierta de instrumentos")
        return []
# ===================================================================================
# BLOQUE 3: CONEXIÓN Y DESCONEXIÓN DE INSTRUMENTOS
# ===================================================================================

class PalmSensConnectionError(Exception):
    """Error personalizado para fallos de conexión PalmSens"""
    pass


def conectar_instrumento(serial: str = None,
                         transport: str = None,
                         address: str = None,
                         timeout_ms: int = 10000):
    """
    Conecta con un instrumento PalmSens usando serial o address.
    Retorna el objeto 'instrumento' del SDK.
    """
    dispositivos = descubrir_instrumentos()
    if not dispositivos:
        raise PalmSensConnectionError("No hay instrumentos disponibles.")

    # Selección del dispositivo
    objetivo = None
    if serial:
        matches = [d for d in dispositivos if d.get('serial') == serial]
        if not matches:
            raise PalmSensConnectionError(f"No se encontró instrumento con serial {serial}.")
        objetivo = matches[0]
    elif address:
        matches = [d for d in dispositivos if d.get('address') == address]
        if not matches:
            raise PalmSensConnectionError(f"No se encontró instrumento con address {address}.")
        objetivo = matches[0]
    else:
        objetivo = dispositivos[0]  # fallback: primer dispositivo

    if transport:
        objetivo['transport'] = transport

    log.info(f"→ Conectando a {objetivo['name']} "
             f"serial={objetivo.get('serial')} "
             f"via {objetivo['transport']} @ {objetivo.get('address')}")

    try:
        import pspymethods
        instrumento = None

        # Ajusta a los métodos reales de tu SDK
        if objetivo['transport'] == 'USB' and hasattr(pspymethods, "connect_usb"):
            instrumento = pspymethods.connect_usb(objetivo['address'], timeout_ms)
        elif objetivo['transport'] == 'Bluetooth' and hasattr(pspymethods, "connect_bluetooth"):
            instrumento = pspymethods.connect_bluetooth(objetivo['address'], timeout_ms)
        elif objetivo['transport'] == 'TCP' and hasattr(pspymethods, "connect_tcp"):
            host, port = objetivo['address'].split(':')
            instrumento = pspymethods.connect_tcp(host, int(port), timeout_ms)
        else:
            raise PalmSensConnectionError(f"Transporte no soportado o método no disponible: {objetivo['transport']}")

        if instrumento is None:
            raise PalmSensConnectionError("El SDK no retornó objeto instrumento (conexión fallida).")

        log.info("✓ Conexión establecida correctamente.")
        return instrumento

    except Exception as e:
        log.exception("✗ Error durante la conexión al instrumento")
        raise PalmSensConnectionError(str(e))


def estado_instrumento(instrumento) -> dict:
    """
    Retorna estado resumido del instrumento.
    """
    est = {
        'connected': True,
        'device_serial': None,
        'firmware': None,
        'battery': None,
        'last_error': None,
    }
    try:
        est['device_serial'] = getattr(instrumento, 'SerialNumber', None)
        est['firmware'] = getattr(instrumento, 'FirmwareVersion', None)
        if hasattr(instrumento, 'BatteryLevel'):
            est['battery'] = instrumento.BatteryLevel
    except Exception as e:
        est['connected'] = False
        est['last_error'] = str(e)
    log.debug(f"Estado instrumento: {est}")
    return est


def desconectar_instrumento(instrumento):
    """
    Cierra la conexión usando el método del SDK correspondiente.
    """
    try:
        if hasattr(instrumento, "Disconnect"):
            instrumento.Disconnect()
        else:
            import pspymethods
            if hasattr(pspymethods, "disconnect"):
                pspymethods.disconnect(instrumento)
        log.info("✓ Instrumento desconectado correctamente.")
    except Exception:
        log.exception("✗ Error al desconectar instrumento")    


# ===================================================================================
# BLOQUE 4: MEDICIÓN CV REMOTA Y NORMALIZACIÓN
# ===================================================================================

import datetime

def iniciar_medicion_cv_remota(instrumento, method_params: dict) -> dict:
    """
    Ejecuta una medición de voltametría cíclica remota en el instrumento y
    retorna un dict compatible con el pipeline de pstrace_session.py:
    {
        'session_info': {...},
        'measurements': [ { 'title', 'timestamp', 'device_serial', 'curve_count', 'curves': [ [ {'potential','current'}, ... ], ... ] } ],
    }
    """
    try:
        import pspymethods

        # 1) Configurar método CV en el instrumento (ajusta a tu SDK real)
        if hasattr(pspymethods, "configure_cv"):
            pspymethods.configure_cv(instrumento, **method_params)
            log.info("✓ Método CV configurado con parámetros: %s", method_params)
        else:
            log.warning("⚠ configure_cv no disponible en pspymethods, usando configuración por defecto")

        # 2) Ejecutar medición y obtener datos
        if not hasattr(pspymethods, "run_cv_and_get_data"):
            raise PalmSensConnectionError("SDK no expone run_cv_and_get_data")
        data = pspymethods.run_cv_and_get_data(instrumento)

        # 3) Normalizar curvas
        curvas_normalizadas = []
        for ciclo in data.get("cycles", []):
            if hasattr(ciclo, "GetXValues") and hasattr(ciclo, "GetYValues"):
                xs = [float(x) for x in ciclo.GetXValues()]
                ys = [float(y) for y in ciclo.GetYValues()]
                curvas_normalizadas.append([{"potential": x, "current": y} for x, y in zip(xs, ys)])
            elif isinstance(ciclo, dict) and "X" in ciclo and "Y" in ciclo:
                xs = [float(x) for x in ciclo["X"]]
                ys = [float(y) for y in ciclo["Y"]]
                curvas_normalizadas.append([{"potential": x, "current": y} for x, y in zip(xs, ys)])

        # 4) Construir session_info y measurement
        session_info = {
            "scan_rate": method_params.get("scan_rate"),
            "start_potential": method_params.get("start_potential"),
            "end_potential": method_params.get("end_potential"),
            "software_version": "PSTrace 5.9.3803",
        }

        measurement = {
            "title": "CV remoto",
            "timestamp": datetime.datetime.now(),
            "device_serial": getattr(instrumento, 'SerialNumber', "Unknown"),
            "curve_count": len(curvas_normalizadas),
            "curves": curvas_normalizadas,
        }

        log.info(f"✓ Medición remota completada: {measurement['curve_count']} curvas")
        return {
            "session_info": session_info,
            "measurements": [measurement],
        }

    except Exception:
        log.exception("✗ Error durante medición CV remota")
        raise

# ===================================================================================
# BLOQUE 5: ORQUESTACIÓN CON BD Y GUI
# ===================================================================================

from src.db_connection import conectar_bd as get_connection
from src.insert_data import guardar_sesion, guardar_mediciones
# Nota: ajusta los imports según tu estructura real de proyecto

def ejecutar_sesion_remota(serial: str, method_params: dict, gui_refresh_callback=None):
    """
    Orquesta una sesión remota completa:
    - Conecta al instrumento
    - Ejecuta medición CV
    - Inserta datos en BD
    - Refresca GUI si se pasa callback

    Args:
        serial (str): Número de serie del instrumento
        method_params (dict): Parámetros del método CV
        gui_refresh_callback (callable): Función opcional para refrescar GUI
    """
    conn = None
    instrumento = None
    try:
        # 1) Conexión
        instrumento = conectar_instrumento(serial=serial)

        # 2) Medición remota
        datos = iniciar_medicion_cv_remota(instrumento, method_params)

        # 3) Conexión a BD
        conn = get_connection()

        # 4) Guardar sesión y mediciones
        session_id = guardar_sesion(
            conn,
            filename=f"REMOTE_{serial}",
            info=datos['session_info']
        )
        guardar_mediciones(conn, session_id, datos['measurements'])

        log.info(f"✓ Sesión remota guardada en BD con ID {session_id}")

        # 5) Refrescar GUI
        if gui_refresh_callback:
            gui_refresh_callback()
            log.info("✓ GUI refrescada tras inserción de sesión remota")

        return session_id

    except Exception:
        log.exception("✗ Error durante la ejecución de sesión remota")
        raise
    finally:
        if instrumento:
            desconectar_instrumento(instrumento)
        if conn:
            conn.close()

# ===================================================================================
# BLOQUE 6: ROBUSTEZ Y RESILIENCIA
# ===================================================================================

import time
import random

def conectar_con_reintentos(serial: str = None,
                            address: str = None,
                            intentos: int = 3,
                            base_delay: float = 1.0):
    """
    Intenta conectar al instrumento con reintentos y backoff exponencial.
    """
    for intento in range(1, intentos + 1):
        try:
            instr = conectar_instrumento(serial=serial, address=address)
            est = estado_instrumento(instr)
            if est['connected']:
                log.info(f"✓ Conexión establecida en intento {intento}")
                return instr
        except Exception as e:
            log.warning(f"⚠ Fallo intento {intento}: {e}")
        # Espera exponencial con jitter
        delay = base_delay * (2 ** (intento - 1)) + random.uniform(0, 0.5)
        log.info(f"Reintentando en {delay:.1f} segundos...")
        time.sleep(delay)
    raise PalmSensConnectionError("No se pudo conectar tras múltiples intentos.")


def ejecutar_sesion_remota_segura(serial: str, method_params: dict, gui_refresh_callback=None):
    """
    Igual que ejecutar_sesion_remota, pero con:
    - Conexión robusta (reintentos)
    - Validación de estado antes de medir
    - Manejo seguro de errores
    """
    conn = None
    instrumento = None
    try:
        # 1) Conexión robusta
        instrumento = conectar_con_reintentos(serial=serial)

        # 2) Validar estado antes de medir
        est = estado_instrumento(instrumento)
        if not est['connected']:
            raise PalmSensConnectionError("Instrumento no está en estado conectado.")

        # 3) Medición remota
        datos = iniciar_medicion_cv_remota(instrumento, method_params)

        # 4) Guardar en BD
        conn = get_connection()
        session_id = guardar_sesion(conn,
                                    filename=f"REMOTE_{serial}",
                                    info=datos['session_info'])
        guardar_mediciones(conn, session_id, datos['measurements'])
        log.info(f"✓ Sesión remota guardada en BD con ID {session_id}")

        # 5) Refrescar GUI
        if gui_refresh_callback:
            gui_refresh_callback()
            log.info("✓ GUI refrescada tras inserción de sesión remota")

        return session_id

    except Exception:
        log.exception("✗ Error en sesión remota segura")
        raise
    finally:
        if instrumento:
            try:
                desconectar_instrumento(instrumento)
            except Exception:
                log.warning("⚠ Fallo al desconectar instrumento")
        if conn:
            conn.close()

# ===================================================================================
# BLOQUE 7: INTEGRACIÓN CON GUI
# ===================================================================================

def ejecutar_sesion_remota_gui(serial: str,
                               method_params: dict,
                               gui_refresh_callback=None,
                               on_connect=None,
                               on_disconnect=None):
    """
    Igual que ejecutar_sesion_remota_segura, pero con hooks para GUI:
    - on_connect: se llama al conectar
    - on_disconnect: se llama al desconectar
    - gui_refresh_callback: se llama tras guardar en BD
    """
    conn = None
    instrumento = None
    try:
        instrumento = conectar_con_reintentos(serial=serial)

        if on_connect:
            on_connect(estado_instrumento(instrumento))

        datos = iniciar_medicion_cv_remota(instrumento, method_params)

        conn = get_connection()
        session_id = guardar_sesion(conn,
                                    filename=f"REMOTE_{serial}",
                                    info=datos['session_info'])
        guardar_mediciones(conn, session_id, datos['measurements'])
        log.info(f"✓ Sesión remota guardada en BD con ID {session_id}")

        if gui_refresh_callback:
            gui_refresh_callback()

        return session_id

    except Exception:
        log.exception("✗ Error en sesión remota con GUI")
        raise
    finally:
        if instrumento:
            try:
                desconectar_instrumento(instrumento)
                if on_disconnect:
                    on_disconnect()
            except Exception:
                log.warning("⚠ Fallo al desconectar instrumento")
        if conn:
            conn.close()            
