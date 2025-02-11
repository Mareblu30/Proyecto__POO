import datetime
import hashlib
import json
import os
import subprocess
import time
import socket
import requests
from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)

# API base de IPFS
IPFS_API_BASE = "http://127.0.0.1:{}/api/v0"
NODO_PUERTOS = [5001, 5002, 5003, 5004, 5005]

# Lock para sincronizar la salida
print_lock = threading.Lock()

# Función para esperar hasta que el nodo esté listo y aceptando conexiones en el puerto API
def esperar_a_que_ipfs_este_listo(puerto):
    intentos = 0
    while intentos < 10:  # Intentar durante 10 segundos
        try:
            sock = socket.create_connection(("127.0.0.1", puerto), timeout=5)
            sock.close()
            with print_lock:
                print(f"Nodo en puerto {puerto} está listo")
            return True  # El nodo está listo
        except (socket.timeout, socket.error):
            time.sleep(1)  # Esperar 1 segundo antes de reintentar
            intentos += 1
    with print_lock:
        print(f"El nodo en puerto {puerto} no está listo.")
    return False

# Función para iniciar un nodo IPFS
def iniciar_ipfs_nodo(i):
    puerto_api = 5001 + i  # Puerto API de cada nodo
    puerto_gateway = 8081 + i  # Puerto Gateway de cada nodo
    carpeta_repo = f"ipfs_repo_{i}"  # Carpeta de configuración para cada nodo

    # Crear un directorio diferente para cada nodo si no existe
    if not os.path.exists(carpeta_repo):
        with print_lock:
            print(f"Iniciando IPFS para el nodo {i}...")
        subprocess.run(["ipfs", "init", "--profile", "server"], env={"IPFS_PATH": carpeta_repo})

    # Configurar el nodo con puertos distintos
    subprocess.run(["ipfs", "config", "Addresses.API", f"/ip4/127.0.0.1/tcp/{puerto_api}"], env={"IPFS_PATH": carpeta_repo})
    subprocess.run(["ipfs", "config", "Addresses.Gateway", f"/ip4/127.0.0.1/tcp/{puerto_gateway}"], env={"IPFS_PATH": carpeta_repo})

    # Iniciar el daemon de IPFS en segundo plano
    proceso = subprocess.Popen(["ipfs", "daemon"], env={"IPFS_PATH": carpeta_repo}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with print_lock:
        print(f"🟢 Nodo {i} iniciado en puertos API {puerto_api} y Gateway {puerto_gateway}")

    # Esperar a que el nodo esté completamente inicializado antes de continuar
    if not esperar_a_que_ipfs_este_listo(puerto_api):
        with print_lock:
            print(f"Error al iniciar el Nodo {i}. No se pudo conectar.")
        return None

    return (proceso, puerto_api)

# Función para iniciar los nodos IPFS en paralelo
def iniciar_ipfs_nodos_paralelo(cantidad_nodos):
    nodos = []
    with ThreadPoolExecutor(max_workers=cantidad_nodos) as executor:
        futures = [executor.submit(iniciar_ipfs_nodo, i) for i in range(cantidad_nodos)]
        for future in futures:
            nodo = future.result()
            if nodo:
                nodos.append(nodo)
    return nodos

# Función para conectar los nodos entre sí
def conectar_nodos_ipfs(cantidad_nodos):
    for i in range(cantidad_nodos):
        puerto_api = 5001 + i
        for j in range(cantidad_nodos):
            if i != j:
                puerto_peer = 5001 + j
                direccion_peer = f"/ip4/127.0.0.1/tcp/{puerto_peer}"

                # Conectar el nodo actual con el otro nodo
                try:
                    response = requests.post(f"http://127.0.0.1:{puerto_api}/api/v0/swarm/connect?arg={direccion_peer}")
                    if response.status_code == 200:
                        with print_lock:
                            print(f"🔗 Nodo {i} conectado a {j}")
                    else:
                        with print_lock:
                            print(f"⚠️ Error al conectar Nodo {i} con {j}: {response.text}")
                except requests.exceptions.RequestException as e:
                    with print_lock:
                        print(f"Excepción al conectar Nodo {i} con {j}: {e}")

# Llamar la función para iniciar los 5 nodos en paralelo
nodos_ipfs = iniciar_ipfs_nodos_paralelo(5)

# Llamar la función para conectar los nodos
conectar_nodos_ipfs(5)

class IPFSManager:
    """Clase para manejar la conexión con IPFS y la gestión de nodos."""
    def __init__(self, puerto):
        self.ipfs_api = IPFS_API_BASE.format(puerto)
        self.puerto = puerto

    def subir_archivo(self, file):
        """Sube un archivo a IPFS."""
        files = {'file': (file.filename, file.stream, file.content_type)}
        response = requests.post(self.ipfs_api + "/add", files=files)
        if response.status_code == 200:
            return response.json()["Hash"]
        return None

    def conectar_nodo(self, direccion_peer):
        """Conecta el nodo actual a otro nodo IPFS."""
        response = requests.post(self.ipfs_api + f"/swarm/connect?arg=/ip4/127.0.0.1/tcp/{direccion_peer}")
        if response.status_code != 200:
            with print_lock:
                print(f"Error al conectar al nodo {direccion_peer}: {response.text}")

class Blockchain:
    """Clase que maneja la blockchain."""
    def __init__(self):
        self.chain = []
        self.crear_bloque(prueba=1, hash_anterior='0', documento=None)

    def crear_bloque(self, prueba, hash_anterior, documento):
        bloque = {
            'indice': len(self.chain) + 1,
            'marca_tiempo': str(datetime.datetime.now()),
            'documento': documento,
            'prueba': prueba,
            'hash_anterior': hash_anterior
        }
        self.chain.append(bloque)
        return bloque

    def obtener_bloque_anterior(self):
        return self.chain[-1]

    def prueba_de_trabajo(self, prueba_anterior):
        nueva_prueba = 1
        prueba_valida = False
        while not prueba_valida:
            operacion_hash = hashlib.sha256(str(nueva_prueba**2 - prueba_anterior**2).encode()).hexdigest()
            if operacion_hash[:4] == '0000':
                prueba_valida = True
            else:
                nueva_prueba += 1
        return nueva_prueba

    def calcular_hash(self, bloque):
        bloque_codificado = json.dumps(bloque, sort_keys=True).encode()
        return hashlib.sha256(bloque_codificado).hexdigest()

# Inicializar Blockchain y Nodos IPFS
blockchain = Blockchain()
nodos_ipfs = [IPFSManager(puerto) for puerto in NODO_PUERTOS]

@app.route("/subir_archivo", methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró ningún archivo'}), 400

    file = request.files['file']
    ipfs_hash = nodos_ipfs[0].subir_archivo(file)  # Usa el primer nodo para subir el archivo
    
    if ipfs_hash:
        documento = {'contenido': ipfs_hash, 'tipo': file.content_type, 'fecha': str(datetime.datetime.now())}
        bloque_anterior = blockchain.obtener_bloque_anterior()
        prueba = blockchain.prueba_de_trabajo(bloque_anterior['prueba'])
        hash_anterior = blockchain.calcular_hash(bloque_anterior)
        bloque = blockchain.crear_bloque(prueba, hash_anterior, documento)
        return jsonify({'mensaje': 'Archivo subido a IPFS y registrado en blockchain',
                        'ipfs_hash': ipfs_hash,
                        'bloque': bloque}), 201
    return jsonify({'error': 'No se pudo subir el archivo a IPFS'}), 500

@app.route("/obtener_cadena", methods=['GET'])
def obtener_cadena():
    return jsonify({'cadena': blockchain.chain, 'longitud': len(blockchain.chain)}), 200

@app.route("/obtener_archivo/<ipfs_hash>", methods=['GET'])
def obtener_archivo(ipfs_hash):
    return jsonify({'archivo_url': f"https://ipfs.io/ipfs/{ipfs_hash}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)