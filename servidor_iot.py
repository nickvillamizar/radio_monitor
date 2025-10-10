# servidor_iot.py
import socket
import json
import os

HOST = "0.0.0.0"  # Escucha en todas las interfaces
PORT = 5000
BUFFER_SIZE = 4096
DEST_DIR = "archivos_recibidos"

os.makedirs(DEST_DIR, exist_ok=True)

print(f"🌐 Servidor IoT escuchando en {HOST}:{PORT}...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.bind((HOST, PORT))
    server.listen(5)

    while True:
        conn, addr = server.accept()
        print(f"📡 Conexión desde {addr}")
        with conn:
            # Intentar recibir el encabezado JSON
            header_data = b""
            while not header_data.endswith(b"\n"):
                chunk = conn.recv(1)
                if not chunk:
                    break
                header_data += chunk

            if not header_data:
                print("⚠ Conexión vacía.")
                continue

            try:
                header = json.loads(header_data.decode().strip())
                filename = header["filename"]
                size = int(header["size"])
                checksum = header["checksum"]
                print(f"📦 Recibiendo archivo: {filename} ({size/1e6:.2f} MB)")
                conn.sendall(b"ACK")
            except Exception as e:
                print(f"❌ Encabezado inválido: {e}")
                conn.close()
                continue

            # Guardar el archivo
            filepath = os.path.join(DEST_DIR, filename)
            with open(filepath, "wb") as f:
                total_received = 0
                while total_received < size:
                    data = conn.recv(BUFFER_SIZE)
                    if not data:
                        break
                    f.write(data)
                    total_received += len(data)

            print(f"✅ Archivo recibido: {filepath} ({total_received/1e6:.2f} MB)")

            # Confirmar finalización
            conn.sendall(b"EOF_OK")
