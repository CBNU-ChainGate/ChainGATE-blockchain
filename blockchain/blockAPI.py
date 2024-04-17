import time
from flask import Flask, jsonify, request
import requests
from threading import Thread, Event
import socket
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
primary = "192.168.56.1"  # primary 정하는 알고리즘 추가 필요
request_data = None
prepare_event = Event()


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
            get_preparemsg_num += 1     # 응답을 받은 노드 개수 저장
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
    D_m = {
        "date": request_data["date"],
        "time": request_data["time"]
    }

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
        print('pre-prepare > if YES!!')
        N = len(blockchain.chain) + 1
        # date와 time 값 추출(JSON 형태)
        D_m = {
            "date": message['data']["date"],
            "time": message['data']["time"]
        }
        preprepare_message = {
            'type': 'PREPREPARE',
            'view': view,   # 메세지가 전송되는 view
            'seq': N,       # 요청의 시퀀스 번호
            'digest': D_m   # 요청 데이터의 요약본
        }
        # 모든 노드에 pre-prepare 메세지 전송
        for node in blockchain.nodes:
            send(node, preprepare_message)
    else:
        return jsonify({'message': '~Not Primary node~'}), 400
    return jsonify({'message': 'Pre-prepare message sended'}), 200


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    print("~~Validating the message~~")
    message = request.get_json()

    print('Before) is_set(): ', end='')
    print(prepare_event.is_set())
    # set()이 될 때까지 wait (new_transaction 함수에서 request_data를 할당해야 set())
    prepare_event.wait()
    print('After) is_set(): ', end='')
    print(prepare_event.is_set())

    # pre-prepare 메세지에 대한 검증
    if validate_preprepare(message):
        print('prepare > if YES!!')
        log.append(message)  # pre-prepare 메세지 수집
        # for문을 비동기로 처리
        threads = []
        for node in blockchain.nodes:
            prepare_thread = Thread(target=send, args=(node, {
                'type': 'PREPARE',
                'view': view+1,
                'seq': message['seq'],
                'node_id': node_id
            }))
            threads.append(prepare_thread)
            prepare_thread.start()

        # # 모든 스레드의 종료를 기다림
        # for thread in threads:
        #     thread.join()
    else:
        prepare_event.clear()
        return jsonify({'message': 'Invalid PRE-PREPARE message!'}), 400
    prepare_event.clear()
    return jsonify({'message': 'Pre-prepare message validated'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    global state, log, request_data
    message = request.get_json()
    print("~~COMMIT~~")
    preprepare_msg_list = [m for m in log if m['type'] ==
                           'PREPREPARE' and m['view'] == message['view'] and m['seq'] == message['seq']]
    prepare_msg_list = [m for m in log if m['type'] == 'PREPARE' and m['view']
                        == message['view'] and m['seq'] == message['seq']]
    if len(preprepare_msg_list) > 2/3 * len(blockchain.nodes) and len(prepare_msg_list) > 2/3 * len(blockchain.nodes):
        # log에서 preprepare_msg_list와 prepare_msg_list에 있는 메시지를 제거
        log = [m for m in log if not (
            m in preprepare_msg_list or m in prepare_msg_list)]

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
    global request_data, state, primary, node_id
    data = request.get_json()
    state = 'REQUEST'
    request_data = data  # 원본 클라이언트 요청 메시지 저장
    client_request = {
        'type': 'REQUEST',
        'data': data
    }
    print(client_request)
    # prepare 함수가 수행될 수 있게 설정
    if request_data:
        prepare_event.set()
    print('is_set(): ', end='')
    print(prepare_event.is_set())
    th_send = Thread(target=send, args=(node_id+port, client_request))
    th_send.start()
    # send(node_id+port, client_request)
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
    prepare_event.clear()
    app.run(host='0.0.0.0', port=80)
