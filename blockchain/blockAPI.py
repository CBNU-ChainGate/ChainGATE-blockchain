import time
from flask import Flask, jsonify, request
import requests
from threading import Thread
import socket
import hashlib
import json
from blockchain import Blockchain

# Flask 앱 초기화
app = Flask(__name__)

# 블록체인 인스턴스 생성
local_ip = socket.gethostbyname(socket.gethostname())
blockchain = Blockchain()
node_id = local_ip
port = ""
state = 'IDLE'
get_preparemsg_num = 0
view = 0
log = []
primary = node_id  # primary 정하는 알고리즘 추가 필요
request_data = None


# def send(receiver, message):
#     print("receiver: "+receiver)
#     if message['type'] == 'REQUEST':
#         response = requests.post(
#             f"http://{receiver}/consensus/request", json=message)
#     elif message['type'] == 'PREPREPARE':
#         response = requests.post(
#             f"http://{receiver}/consensus/preprepare", json=message)
#     elif message['type'] == 'PREPARE':
#         response = requests.post(
#             f"http://{receiver}/consensus/prepare", json=message)
#     elif message['type'] == 'COMMIT':
#         response = requests.post(
#             f"http://{receiver}/consensus/commit", json=message)


# @app.route('/consensus/request', methods=['POST'])
# def handle_request():
#     global request_data
#     message = request.get_json()
#     print("~~REQUEST~~")
#     if node_id == primary:
#         request_data = message  # 원본 클라이언트 요청 메시지 저장
#         N = len(blockchain.chain) + 1
#         D_m = hashlib.sha256(json.dumps(message).encode()).hexdigest()
#         preprepare_message = {
#             'type': 'PREPREPARE',
#             'view': 0,
#             'seq': N,  # 요청의 시퀀스 번호
#             'digest': D_m
#         }
#         for node in blockchain.nodes:
#             send(node, preprepare_message)
#     return jsonify({'message': 'Step request completed'}), 200


def send(receiver, message):
    global get_preparemsg_num
    print("receiver: "+receiver)
    if message['type'] == 'REQUEST':
        response = requests.post(
            f"http://{receiver}/consensus/preprepare", json=message)
    elif message['type'] == 'PREPREPARE':
        response = requests.post(
            f"http://{receiver}/consensus/prepare", json=message)
        if response.status_code == 200:
            get_preparemsg_num += 1     # 응답을 받은 노드 개수 체크
    elif message['type'] == 'PREPARE':
        log.append(message)     # prepare 메세지 수집
        # 다른 노드의 응답을 받을 때까지 대기
        while get_preparemsg_num != len(blockchain.nodes):
            pass
        get_preparemsg_num = 0
        response = requests.post(
            f"http://{receiver}/consensus/commit", json=message)


# pre-prepare 메세지가 정상적인 메세지인지 검증
def validate_preprepare(preprepare_message):
    D_m = hashlib.sha256(json.dumps(request_data).encode()).hexdigest()

    # client가 보낸 data에 이상이 있다면
    if D_m != preprepare_message['digest']:
        return False
    # 메세지의 view나 seq의 값에 이상이 있다면
    if preprepare_message['view'] != view or preprepare_message['seq'] != len(blockchain.chain)+1:
        return False
    return True


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare():
    print("~~Sending Pre-prepare message~~")
    global view
    message = request.get_json()
    if node_id == primary:
        N = len(blockchain.chain) + 1
        D_m = hashlib.sha256(json.dumps(message['data']).encode()).hexdigest()
        preprepare_message = {
            'type': 'PREPREPARE',
            'view': view,   # 메세지가 전송되는 view
            'seq': N,       # 요청의 시퀀스 번호
            'digest': D_m   # 요청 데이터의 요약본
        }
        # 모든 노드에 pre-prepare 메세지 전송
        for node in blockchain.nodes:
            send(node, preprepare_message)
    return jsonify({'message': 'Pre-prepare message sended'}), 200


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    print("~~Validating the message~~")
    message = request.get_json()
    # pre-prepare 메세지에 대한 검증
    if validate_preprepare(message):
        log.append(message)  # pre-prepare 메세지 수집
        for node in blockchain.nodes:
            prepare_message = {
                'type': 'PREPARE',
                'view': view+1,
                'seq': message['seq'],
                'node_id': node_id
            }
            send(node, prepare_message)
    else:
        return jsonify({'message': 'Invalid PRE-PREPARE message!'}), 400
    return jsonify({'message': 'Pre-prepare message validated'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    global state, log, request_data
    message = request.get_json()
    print("~~COMMIT~~")
    if len([m for m in log if m['type'] == 'PREPARE' and m['view'] == message['view'] and m['seq'] == message['seq']]) > 2/3 * len(blockchain.nodes):
        state = 'PreparedCertificate'
        response = requests.get(f"http://{local_ip}/conseneus/reply")
    else:
        return jsonify({'message': 'Failed to commit new block!'}), 400
    return jsonify({'message': 'prepare message committed'}), 200


@app.route('/conseneus/reply')
def handle_reply():
    global request_data
    blockchain.add_transaction(request_data)
    if blockchain.create_block(blockchain.hash(blockchain.get_lastblock())):
        print(f"Node [{node_id}] committed new block")


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


@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    global request_data, state
    data = request.get_json()
    state = 'REQUEST'
    request_data = data  # 원본 클라이언트 요청 메시지 저장
    client_request = {
        'type': 'REQUEST',
        'data': data
    }
    print(client_request)
    send(node_id+port, client_request)
    return jsonify({'message': 'Send Request to node...'}), 201


@app.route('/chain/get', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


def sync_blocks():
    while True:
        if len(blockchain.chain) % 10 == 0 or (time.time() - float(blockchain.chain[-1]['timestamp'])) >= 300:
            if blockchain.synchronize_node():
                print("Blockchain synchronized")
        time.sleep(30)


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
    # sync_thread = Thread(target=sync_blocks)
    # sync_thread.start()
    app.run(host='0.0.0.0', port=80)
