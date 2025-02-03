import datetime
import hashlib
import json
from flask import Flask, jsonify, request

class Document:
    def __init__(self, content, doc_type='general', version='1.0'):
        self.content = content
        self.metadata = {
            'created_at': str(datetime.datetime.now()),
            'type': doc_type,
            'version': version
        }

    def to_dict(self):
        return {
            'content': self.content,
            'metadata': self.metadata
        }

class Transaction:
    def __init__(self, blockchain):
        self.blockchain = blockchain

    def add_document(self, document):
        # Obtener el bloque anterior y realizar el algoritmo de prueba de trabajo
        previous_block = self.blockchain.get_previous_block()
        previous_proof = previous_block['proof']
        proof = self.blockchain.proof_of_work(previous_proof)
        previous_hash = self.blockchain.hash(previous_block)

        # Crear el bloque con el nuevo documento
        block = self.blockchain.create_block(proof, previous_hash, document.to_dict())

        return block

class DocumentBlockchain:
    def __init__(self):
        self.chain = []
        # Se crea el bloque génesis
        self.create_block(proof=1, previous_hash='0', document=None)

    def create_block(self, proof, previous_hash, document):
        # Crear un nuevo bloque
        block = {
            'index': len(self.chain) + 1,
            'timestamp': str(datetime.datetime.now()),
            'document': document,
            'proof': proof,
            'previous_hash': previous_hash
        }
        self.chain.append(block)
        return block

    def get_previous_block(self):
        return self.chain[-1]

    def proof_of_work(self, previous_proof):
        # Algoritmo de prueba de trabajo (minado)
        new_proof = 1
        check_proof = False

        while check_proof is False:
            hash_operation = hashlib.sha256(str(new_proof**2 - previous_proof**2).encode()).hexdigest()
            if hash_operation[:4] == '0000':
                check_proof = True
            else:
                new_proof += 1
        return new_proof

    def hash(self, block):
        # Crear un hash de un bloque
        encoded_block = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(encoded_block).hexdigest()

    def is_chain_valid(self, chain):
        # Verificar si la cadena es válida
        previous_block = chain[0]
        block_index = 1
        while block_index < len(chain):
            block = chain[block_index]
            if block['previous_hash'] != self.hash(previous_block):
                return False
            previous_proof = previous_block['proof']
            proof = block['proof']
            hash_operation = hashlib.sha256(str(proof**2 - previous_proof**2).encode()).hexdigest()
            if hash_operation[:4] != '0000':
                return False
            previous_block = block
            block_index += 1
        return True

# Configuración de Flask
app = Flask(__name__)
blockchain = DocumentBlockchain()
transaction = Transaction(blockchain)

@app.route("/add_document", methods=['POST'])
def add_document():
    # Obtener los datos del documento desde la solicitud
    data = request.get_json()

    # Verifica si los datos contienen contenido
    if not data or 'content' not in data:
        return jsonify({'error': 'No document content provided'}), 400

    # Crear el documento usando la clase Document
    document = Document(content=data['content'], doc_type=data.get('type', 'general'))

    # Usar la clase Transaction para agregar el documento a la cadena de bloques
    block = transaction.add_document(document)

    response = {
        'message': 'Documento añadido exitosamente',
        'block': block
    }

    return jsonify(response), 201

@app.route("/get_chain", methods=['GET'])
def get_chain():
    # Obtener la cadena de bloques y devolverla
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)