from time import time
from flask import Flask, jsonify, request
from threading import Thread
from blockchain import Blockchain, PBFTNode
import socket

# Flask 앱 초기화
app = Flask(__name__)

# 블록체인 인스턴스 생성
local_ip = socket.gethostbyname(socket.gethostname())
blockchain = Blockchain()
pbft_node = PBFTNode(local_ip, blockchain)


# 노드 등록
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.add_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201


# 새로운 트랜잭션 추가
@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    data = request.get_json()
    client_request = {
        'type': 'REQUEST',
        'data': data
    }
    pbft_node.handle_request(client_request)
    return jsonify({'message': 'Send Request to node'}), 201


# 블록체인 데이터 가져오기
@app.route('/chain/get', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


# 노드 동기화(자동)
def sync_blocks():
    while True:
        if len(blockchain.chain) % 10 == 0 or (time.time() - float(blockchain.chain[-1]['timestamp'])) >= 300:
            if blockchain.synchronize_node():
                print("Blockchain synchronized")
        time.sleep(30)  # 1분마다 체크


# 노드 동기화(수동)           (Debugging)
@app.route('/nodes/sync', methods=['GET'])
def sync():
    if blockchain.synchronize_node():
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == "__main__":
    # 노드 동기화 함수 실행
    sync_thread = Thread(target=sync_blocks)
    sync_thread.start()
    app.run(host='0.0.0.0', port=5000)
