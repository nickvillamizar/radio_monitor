import socket
import json
import os
import argparse
from tqdm import tqdm

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_cliente.json")

def cargar_config():
    """Carga la configuración desde config_cliente.json o crea una nueva si no existe."""
    if not os.path.exists(CONFIG_PATH):
        print("⚙ No se encontró config_cliente.json, creando archivo nuevo con valores por defecto...")
        config = {
            "HOST": "10.253.30.118",
            "PORT": 5000,
            "BUFFER_SIZE": 4096
        }
        guardar_config(config)
        return config

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
        # Validar que tenga las claves correctas
        if not all(k in config for k in ["HOST", "PORT", "BUFFER_SIZE"]):
            raise KeyError("Archivo de configuración incompleto.")
        return config
    except Exception as e:
        print(f"❌ Error al leer configuración: {e}")
        return None

def guardar_config(config):
    """Guarda la configuración actual en config_cliente.json."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    print(f"✅ Configuración guardada en {CONFIG_PATH}")

def configurar():
    """Permite al usuario modificar la IP y el puerto de forma amigable."""
    config = cargar_config() or {}
    print("\n🧠 Configuración actual:")
    print(json.dumps(config, indent=4))
    
    print("\n✏ Ingrese nuevos valores (presione Enter para dejar el actual):")
    host = input(f"IP actual [{config.get('HOST', '')}]: ") or config.get('HOST', '127.0.0.1')
    port = input(f"Puerto actual [{config.get('PORT', '')}]: ") or config.get('PORT', 5000)
    buffer_size = input(f"Tamaño de buffer [{config.get('BUFFER_SIZE', '')}]: ") or config.get('BUFFER_SIZE', 4096)

    config["HOST"] = host
    config["PORT"] = int(port)
    config["BUFFER_SIZE"] = int(buffer_size)

    guardar_config(config)
    print("✅ Configuración actualizada con éxito.")

def enviar_archivo(ruta_archivo):
    """Envía un archivo al servidor usando la configuración actual."""
    config = cargar_config()
    if not config:
        print("❌ No se pudo cargar configuración.")
        return

    host = config["HOST"]
    port = config["PORT"]
    buffer_size = config["BUFFER_SIZE"]

    if not os.path.exists(ruta_archivo):
        print("❌ Archivo no encontrado:", ruta_archivo)
        return

    print(f"📡 Conectando a {host}:{port}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print(f"✅ Conectado a {host}:{port}")
        s.sendall(os.path.basename(ruta_archivo).encode() + b"\n")

        with open(ruta_archivo, "rb") as f, tqdm(
            total=os.path.getsize(ruta_archivo),
            unit="B", unit_scale=True, desc="Enviando"
        ) as barra:
            while (chunk := f.read(buffer_size)):
                s.sendall(chunk)
                barra.update(len(chunk))
        print("✅ Archivo enviado correctamente.")

def main():
    parser = argparse.ArgumentParser(description="Cliente IoT mejorado con configuración amigable.")
    parser.add_argument("--config", action="store_true", help="Abrir configuración interactiva")
    parser.add_argument("--send", type=str, help="Enviar archivo al servidor")
    args = parser.parse_args()

    if args.config:
        configurar()
    elif args.send:
        enviar_archivo(args.send)
    else:
        print("Uso:")
        print("  python cliente_iot.py --config          # Modificar IP/puerto")
        print("  python cliente_iot.py --send archivo.txt  # Enviar archivo al servidor")

if __name__ == "__main__":
    main()
