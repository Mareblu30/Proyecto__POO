import datetime
import hashlib
import json
import requests
from flask import Flask, jsonify, request

# Configuración de Flask
app = Flask(__name__)

# API de IPFS (debe estar corriendo el daemon)
IPFS_API = "http://127.0.0.1:5001/api/v0"

class IPFSManager:
    "Clase para manejar la conexión con IPFS"
    @staticmethod
    def subir_archivo(file):
        files = {'file': (file.filename, file.stream, file.content_type)}
        response = requests.post(IPFS_API + "/add", files=files)
        if response.status_code == 200:
            return response.json()["Hash"]
        return None

class BlockchainManager:
    "Clase para manejar la cadena de bloques"
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

    def es_cadena_valida(self, cadena):
        bloque_anterior = cadena[0]
        indice_bloque = 1
        while indice_bloque < len(cadena):
            bloque = cadena[indice_bloque]
            if bloque['hash_anterior'] != self.calcular_hash(bloque_anterior):
                return False
            prueba_anterior = bloque_anterior['prueba']
            prueba = bloque['prueba']
            operacion_hash = hashlib.sha256(str(prueba**2 - prueba_anterior**2).encode()).hexdigest()
            if operacion_hash[:4] != '0000':
                return False
            bloque_anterior = bloque
            indice_bloque += 1
        return True

# Inicializar blockchain y gestor de IPFS
blockchain = BlockchainManager()
ipfs_manager = IPFSManager()

@app.route("/subir_archivo", methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró ningún archivo'}), 400

    file = request.files['file']
    ipfs_hash = ipfs_manager.subir_archivo(file)
    
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