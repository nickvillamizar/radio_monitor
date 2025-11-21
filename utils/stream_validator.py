# archivo: utils/stream_validator.py - Validador de URLs de streaming
"""
Sistema de validación y diagnóstico de URLs de streaming.
Identifica emisoras problemáticas y registra métricas de accesibilidad.
"""

import requests
import logging
import socket
import time
from typing import Dict, Tuple, List, Optional
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Configuración de timeouts y reintentos
CONNECT_TIMEOUT = 10  # segundos para conectarse
READ_TIMEOUT = 5      # segundos para primera respuesta
MAX_RETRIES = 3
RETRY_DELAY = 2

# User agents variados para evitar bloqueos
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'VLC/3.0.0',
    'RadioMonitor/3.0 (Diagnostic Tool)'
]


class StreamValidator:
    """Validador de URLs de streaming con diagnóstico detallado."""
    
    def __init__(self):
        self.session = requests.Session()
        self.results_cache = {}
    
    def validate_url(self, url: str, verbose: bool = False) -> Dict[str, any]:
        """
        Valida una URL de streaming y retorna diagnóstico detallado.
        
        Returns:
            {
                'url': str,
                'valid': bool,
                'status_code': int | None,
                'is_reachable': bool,
                'is_streaming_server': bool,
                'response_time_ms': float,
                'headers_received': bool,
                'content_type': str | None,
                'error': str | None,
                'diagnosis': str,  # Explicación legible
                'timestamp': str
            }
        """
        
        if not url:
            return self._error_response(url, "URL vacía", "URL_EMPTY")
        
        # Limpiar URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        
        # Validar URL bien formada
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return self._error_response(url, "URL malformada", "MALFORMED_URL")
        except Exception as e:
            return self._error_response(url, f"Error parseando URL: {e}", "PARSE_ERROR")
        
        # Intentar conexión
        result = self._attempt_connection(url, verbose)
        
        # Guardar en caché
        self.results_cache[url] = result
        
        return result
    
    def _attempt_connection(self, url: str, verbose: bool = False) -> Dict:
        """Intenta conectarse a la URL con reintentos."""
        
        headers = {
            'User-Agent': USER_AGENTS[0],
            'Accept': '*/*',
            'Range': 'bytes=0-10000'  # Solo primeros bytes
        }
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                if verbose:
                    logger.info(f"  [Intento {attempt + 1}/{MAX_RETRIES}] {url}")
                
                # Usar timeout real
                response = self.session.head(
                    url,
                    headers=headers,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    allow_redirects=True,
                    verify=False
                )
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Diagnosticar basado en respuesta
                return self._diagnose_response(url, response, elapsed_ms)
                
            except requests.exceptions.Timeout:
                last_error = "TIMEOUT"
                if verbose:
                    logger.warning(f"    ⏱️  Timeout")
            except requests.exceptions.ConnectionError:
                last_error = "CONNECTION_ERROR"
                if verbose:
                    logger.warning(f"    ❌ Error de conexión")
            except requests.exceptions.RequestException as e:
                last_error = f"REQUEST_ERROR: {str(e)[:50]}"
                if verbose:
                    logger.warning(f"    ❌ {last_error}")
            except Exception as e:
                last_error = f"UNKNOWN_ERROR: {str(e)[:50]}"
                if verbose:
                    logger.warning(f"    ❌ {last_error}")
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        
        # Todos los intentos fallaron
        elapsed_ms = (time.time() - start_time) * 1000
        
        return {
            'url': url,
            'valid': False,
            'status_code': None,
            'is_reachable': False,
            'is_streaming_server': False,
            'response_time_ms': elapsed_ms,
            'headers_received': False,
            'content_type': None,
            'error': last_error or 'UNKNOWN_ERROR',
            'diagnosis': f'No se pudo conectar después de {MAX_RETRIES} intentos. Último error: {last_error}',
            'timestamp': datetime.now().isoformat()
        }
    
    def _diagnose_response(self, url: str, response, elapsed_ms: float) -> Dict:
        """Diagnostica la respuesta HTTP."""
        
        status_code = response.status_code
        is_reachable = 200 <= status_code < 400
        
        content_type = response.headers.get('Content-Type', '').lower()
        is_streaming = any(x in content_type for x in [
            'audio', 'mpeg', 'ogg', 'wav', 'aac', 'flac',
            'application/octet-stream', 'stream'
        ])
        
        # Diagnóstico inteligente
        diagnosis = ""
        
        if status_code == 200:
            if is_streaming:
                diagnosis = "✅ URL válida - Streaming activo"
                valid = True
            else:
                diagnosis = f"⚠️  URL responde pero no es streaming (Content-Type: {content_type[:50]})"
                valid = True  # Accesible pero no streaming
        elif status_code == 206:
            diagnosis = "✅ URL válida - Streaming parcial (Range request)"
            valid = True
            is_streaming = True
        elif 300 <= status_code < 400:
            diagnosis = f"🔀 Redirect ({status_code}) - Posible redirección a m3u/pls"
            valid = True
            is_streaming = True
        elif status_code == 401 or status_code == 403:
            diagnosis = f"🔐 Acceso denegado ({status_code}) - Requiere autenticación"
            valid = False
        elif status_code == 404:
            diagnosis = "❌ No encontrado (404) - URL no válida"
            valid = False
        elif status_code == 503:
            diagnosis = "⚠️  Servicio no disponible (503) - Puede ser temporal"
            valid = False
        else:
            diagnosis = f"❓ Código desconocido ({status_code})"
            valid = (status_code < 400)
        
        return {
            'url': url,
            'valid': valid,
            'status_code': status_code,
            'is_reachable': is_reachable,
            'is_streaming_server': is_streaming,
            'response_time_ms': elapsed_ms,
            'headers_received': True,
            'content_type': content_type[:100] if content_type else None,
            'error': None,
            'diagnosis': diagnosis,
            'timestamp': datetime.now().isoformat()
        }
    
    def _error_response(self, url: str, error_msg: str, error_code: str) -> Dict:
        """Respuesta de error estándar."""
        return {
            'url': url,
            'valid': False,
            'status_code': None,
            'is_reachable': False,
            'is_streaming_server': False,
            'response_time_ms': 0,
            'headers_received': False,
            'content_type': None,
            'error': error_code,
            'diagnosis': f"❌ {error_msg}",
            'timestamp': datetime.now().isoformat()
        }
    
    def validate_multiple(self, emisoras: List, verbose: bool = False) -> Dict[int, Dict]:
        """
        Valida múltiples emisoras.
        
        Args:
            emisoras: Lista de objetos Emisora
            
        Returns:
            {emisora_id: resultado}
        """
        results = {}
        
        for i, emisora in enumerate(emisoras, 1):
            logger.info(f"[{i}/{len(emisoras)}] Validando: {emisora.nombre} ({emisora.url_stream})")
            result = self.validate_url(emisora.url_stream, verbose=verbose)
            results[emisora.id] = result
        
        return results
    
    def generate_report(self, emisoras: List, results: Dict) -> str:
        """
        Genera reporte de diagnóstico en formato legible.
        """
        report = []
        report.append("=" * 80)
        report.append("REPORTE DE DIAGNÓSTICO DE EMISORAS")
        report.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")
        
        # Estadísticas
        total = len(results)
        valid = sum(1 for r in results.values() if r['valid'])
        reachable = sum(1 for r in results.values() if r['is_reachable'])
        streaming = sum(1 for r in results.values() if r['is_streaming_server'])
        
        report.append(f"📊 RESUMEN")
        report.append(f"  - Total de emisoras: {total}")
        report.append(f"  - URLs válidas: {valid} ({valid*100//total}%)")
        report.append(f"  - URLs alcanzables: {reachable} ({reachable*100//total}%)")
        report.append(f"  - Servidores streaming: {streaming} ({streaming*100//total}%)")
        report.append("")
        
        # Detalles por emisora
        report.append("=" * 80)
        report.append("ANÁLISIS POR EMISORA")
        report.append("=" * 80)
        report.append("")
        
        # Ordenar por validez y nombre
        emisoras_dict = {e.id: e for e in emisoras}
        sorted_results = sorted(
            results.items(),
            key=lambda x: (not x[1]['valid'], emisoras_dict.get(x[0], type('', (), {'nombre': 'Unknown'})()).nombre)
        )
        
        for emisora_id, result in sorted_results:
            emisora = emisoras_dict.get(emisora_id)
            if not emisora:
                continue
            
            report.append(f"📻 {emisora.nombre}")
            report.append(f"   URL: {result['url']}")
            report.append(f"   {result['diagnosis']}")
            
            if result['status_code']:
                report.append(f"   Status: {result['status_code']}")
            if result['response_time_ms']:
                report.append(f"   Tiempo respuesta: {result['response_time_ms']:.0f}ms")
            if result['content_type']:
                report.append(f"   Content-Type: {result['content_type']}")
            if result['error']:
                report.append(f"   Error: {result['error']}")
            
            report.append("")
        
        # Recomendaciones
        report.append("=" * 80)
        report.append("RECOMENDACIONES")
        report.append("=" * 80)
        report.append("")
        
        problematic = [r for r in results.values() if not r['valid']]
        if problematic:
            report.append(f"⚠️  Se encontraron {len(problematic)} emisoras con problemas:")
            for i, result in enumerate(problematic, 1):
                emisora = next((e for e in emisoras if e.id == next((k for k, v in results.items() if v == result), None)), None)
                if emisora:
                    report.append(f"   {i}. {emisora.nombre}: {result['diagnosis']}")
            report.append("")
            report.append("   Acciones sugeridas:")
            report.append("   - Verificar que las URLs sean correctas")
            report.append("   - Contactar a proveedores de streaming")
            report.append("   - Revisar configuración de firewall/proxy")
            report.append("   - Considerar usar mirrors/backups de URLs")
        else:
            report.append("✅ Todas las emisoras están accesibles")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)


# Instancia global
validator = StreamValidator()
