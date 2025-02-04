import datetime
import hashlib
import json
import os
import requests
from flask import Flask, jsonify, request

# Configuración de Flask
app = Flask(__name__)

# API de IPFS (debe estar corriendo el daemon en cada nodo)
IPFS_API = "http://127.0.0.1:5001/api/v0"

# Lista de nodos en la red (ajustar según sea necesario)
nodos = [
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
    "http://127.0.0.1:5003",
    "http://127.0.0.1:5004",
]

class Documento:
    def __init__(self, contenido, tipo='general', version='1.0'):
        self.contenido = contenido
        self.metadatos = {
            'creado_en': str(datetime.datetime.now()),
            'tipo': tipo,
            'version': version
        }

    def a_diccionario(self):
        return {
            'contenido': self.contenido,
            'metadatos': self.metadatos
        }

class BlockchainDocumentos:
    def __init__(self):
        self.cadena = []
        self.crear_bloque(prueba=1, hash_anterior='0', documento=None)

    def crear_bloque(self, prueba, hash_anterior, documento):
        bloque = {
            'indice': len(self.cadena) + 1,
            'timestamp': str(datetime.datetime.now()),
            'documento': documento,
            'prueba': prueba,
            'hash_anterior': hash_anterior
        }
        self.cadena.append(bloque)
        return bloque

    def obtener_bloque_anterior(self):
        return self.cadena[-1]

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

# Inicializar blockchain
documentos_blockchain = BlockchainDocumentos()

@app.route("/subir_archivo", methods=['POST'])
def subir_archivo():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se encontró ningún archivo'}), 400

    archivo = request.files['archivo']
    archivos = {'file': (archivo.filename, archivo.stream, archivo.content_type)}

    # Subir archivo a IPFS
    respuesta = requests.post(IPFS_API + "/add", files=archivos)
    if respuesta.status_code == 200:
        ipfs_hash = respuesta.json()["Hash"]

        # Crear documento en la blockchain con el hash de IPFS
        documento = Documento(contenido=ipfs_hash, tipo=archivo.content_type)
        bloque_anterior = documentos_blockchain.obtener_bloque_anterior()
        prueba = documentos_blockchain.prueba_de_trabajo(bloque_anterior['prueba'])
        hash_anterior = documentos_blockchain.calcular_hash(bloque_anterior)
        bloque = documentos_blockchain.crear_bloque(prueba, hash_anterior, documento.a_diccionario())

        return jsonify({'mensaje': 'Archivo subido a IPFS y registrado en blockchain',
                        'ipfs_hash': ipfs_hash,
                        'bloque': bloque}), 201
    return jsonify({'error': 'No se pudo subir el archivo a IPFS'}), 500

@app.route("/obtener_cadena", methods=['GET'])
def obtener_cadena():
    return jsonify({'cadena': documentos_blockchain.cadena, 'longitud': len(documentos_blockchain.cadena)}), 200

@app.route("/obtener_archivo/<ipfs_hash>", methods=['GET'])
def obtener_archivo(ipfs_hash):
    return jsonify({'archivo_url': f"https://ipfs.io/ipfs/{ipfs_hash}"}), 200

@app.route("/sincronizar_nodos", methods=['GET'])
def sincronizar_nodos():
    for nodo in nodos:
        try:
            respuesta = requests.get(f"{nodo}/obtener_cadena")
            if respuesta.status_code == 200:
                datos_nodo = respuesta.json()
                cadena_nodo = datos_nodo['cadena']
                if len(cadena_nodo) > len(documentos_blockchain.cadena) and documentos_blockchain.es_cadena_valida(cadena_nodo):
                    documentos_blockchain.cadena = cadena_nodo
        except requests.exceptions.RequestException:
            continue
    return jsonify({'mensaje': 'Nodos sincronizados', 'cadena': documentos_blockchain.cadena}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)