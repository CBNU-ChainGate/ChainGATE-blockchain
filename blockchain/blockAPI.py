import time
from flask import Flask, jsonify, request
import requests
from threading import Thread
import socket
import hashlib
import json
from urllib.parse import urlparse
from blockchain import Blockchain


# Flask 앱 초기화
app = Flask(__name__)

# 블록체인 인스턴스 생성
local_ip = socket.gethostbyname(socket.gethostname())
blockchain = Blockchain()
# pbft_node = PBFTNode(local_ip, blockchain)

node_id = local_ip
state = 'IDLE'
view = 0
log = []
primary = list(blockchain.nodes)[0] if blockchain.nodes else None
request_message = None


def send(self, receiver, message):
    node = "http://"+receiver
    if message['type'] == 'REQUEST':
        response = requests.post(node+"/consensus/request", data=message)
    elif message['type'] == 'PREPREPARE':
        response = requests.post(node+"/consensus/preprepare", data=message)
    elif message['type'] == 'PREPARE':
        response = requests.post(node+"/consensus/prepare", data=message)
    elif message['type'] == 'COMMIT':
        response = requests.post(node+"/consensus/commit", data=message)


@app.route('/consensus/request', methods=['POST'])
def handle_request(self, message):
    print("~~REQUEST~~")
    global request_message
    if node_id == primary:
        request_message = message  # 원본 클라이언트 요청 메시지 저장
        N = len(blockchain.chain) + 1
        D_m = hashlib.sha256(json.dumps(message).encode()).hexdigest()
        preprepare_message = {
            'type': 'PREPREPARE',
            'view': 0,
            'seq': N,  # 요청의 시퀀스 번호
            'digest': D_m
        }
        for node in blockchain.nodes:
            send(node, preprepare_message)


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare(self, message):
    print("~~PREPREPARE~~")
    if state == 'IDLE':
        state = 'PREPREPARE'
        log.append(message)
        D_m = hashlib.sha256(json.dumps(message).encode()).hexdigest()
        prepare_message = {
            'type': 'PREPARE',
            'view': 1,
            'seq': message['seq'],
            'digest': D_m,
            'node_id': node_id
        }
        for node in blockchain.nodes:  # 이 부분 API request로 고치기 #########
            send(node, prepare_message)


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare(self, message):
    print("~~PREPARE~~")
    if state == 'PREPREPARE':
        log.append(message)
        if len([m for m in log if m['type'] == 'PREPARE' and m['view'] == message['view'] and m['seq'] == message['seq']]) > 2/3 * len(blockchain.nodes):
            for node in blockchain.nodes:
                commit_message = {
                    'type': 'COMMIT',
                    'view': 2,
                    'seq': message['seq'],
                    'node_id': node_id
                }
                # 이 부분 API request로 고치기 #########
                send(node, commit_message)


@app.route('/consensus/commit', methods=['POST'])
def handle_commit(self, message):
    print("~~COMMIT~~")
    if state == 'PREPARE':
        log.append(message)
        if len([m for m in log if m['type'] == 'COMMIT' and m['view'] == message['view'] and m['seq'] == message['seq']]) > 2/3 * len(blockchain.nodes):
            state = 'IDLE'
            blockchain.add_transaction(request_message)
            if blockchain.create_block(blockchain.hash(blockchain.get_lastblock())):
                print(f"Node [{node_id}] committed new block")
            else:
                print("Error: Failed to commit new block!")


"""============================================================================="""


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
    print(client_request)
    send(node_id, client_request)
    return jsonify({'message': 'Send Request to node'}), 201


# 블록체인 데이터 가져오기
@app.route('/chain/get', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


"""============================================================================="""


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
