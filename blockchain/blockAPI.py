import time
from flask import Flask, jsonify, request
import requests
from threading import Thread, Event
import socket
import json
from blockchain import Blockchain

app = Flask(__name__)

local_ip = socket.gethostbyname(socket.gethostname())
blockchain = Blockchain()
node_id = local_ip  # 어떻게 처리할지 재고려
port = ""
state = 'IDLE'
get_msg_num = 0
view = 0
log = []
primary = "192.168.0.31"  # primary 정하는 알고리즘 추가 필요
request_data = None
prepare_event = Event()
prepare_certificate = False
commit_certificate = False


def send(receiver, message):
    """Send a message to the node through API"""
    print("receiver: "+receiver)  # Debugging
    if message['type'] == 'REQUEST':
        print("===============REQUEST===============")
        response = requests.post(
            f"http://{receiver}/consensus/request", json=message)

    elif message['type'] == 'PREPREPARE':
        print("===============PRE-PREPARE===============")
        response = requests.post(
            f"http://{receiver}/consensus/preprepare", json=message)

    elif message['type'] == 'PREPARE':
        print("===============PREPARE===============")
        log.append(message)         # prepare 메세지 수집
        response = requests.post(
            f"http://{receiver}/consensus/prepare", json=message)

    elif message['type'] == 'COMMIT':
        print("===============COMMIT===============")
        log.append(message)         # commit 메세지 수집
        # # 다른 노드의 응답을 받을 때까지 대기
        # get_msg_num += 1     # 응답을 받은 노드 개수 저장
        # while get_msg_num != len(blockchain.nodes):
        #     pass
        # get_msg_num = 0
        response = requests.post(
            f"http://{receiver}/consensus/commit", json=message)


def wait_msg(caller):
    """다른 노드의 응답을 받을 때까지 대기"""
    global get_msg_num
    get_msg_num += 1     # 응답을 받은 노드 개수 저장
    while True:
        if caller == 'prepare' and get_msg_num != len(blockchain.nodes)-1:
            break
        elif caller == 'commit' and get_msg_num != len(blockchain.nodes):
            break
    get_msg_num = 0
    print("*****GET ALL MESSAGE*****")


def validate_preprepare(preprepare_message):
    """pre-prepare 메세지가 정상적인 메세지인지 검증"""

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


def reply_request():
    blockchain.add_transaction(request_data)
    last_block = blockchain.get_lastblock()
    if blockchain.create_block(blockchain.hash(last_block)):
        print(f"** Node [{node_id}] added a new block **")
        return True
    return False


@app.route('/consensus/request', methods=['POST'])
def handle_request():
    print("~~Sending Pre-prepare message~~")  # Debugging
    global view
    message = request.get_json()
    if node_id == primary:
        print('Request > if YES!!')  # Debugging
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


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare():
    print("~~Validating the message~~")  # Debugging
    message = request.get_json()

    # print('Before) is_set(): ', end='')  # Debugging
    # print(prepare_event.is_set())
    # set()이 될 때까지 wait (new_transaction 함수에서 request_data를 할당해야 set())
    prepare_event.wait()
    # print('After) is_set(): ', end='')  # Debugging
    # print(prepare_event.is_set())

    # pre-prepare 메세지에 대한 검증
    if validate_preprepare(message):  # 검증방법 재고려 필요 XXXXXXXXXXXXXXXXXXx
        print('preprepare > if YES!!')  # Debugging
        log.append(message)  # pre-prepare 메세지 수집

        # for문을 비동기로 처리
        threads = []
        for node in blockchain.nodes:
            prepare_thread = Thread(target=send, args=(node, {
                'type': 'PREPARE',
                'view': view+1,
                'seq': message['seq'],
                'digest': message['digest'],
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


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    global prepare_certificate, log
    message = request.get_json()
    wait_msg('prepare')  # 모든 노드한테서 메세지를 받을 때까지 기다리기
    print("~~PREPARE~~")  # Debugging
    prepare_msg_list = [m for m in log if m['type'] == 'PREPARE' and m['view']
                        == message['view'] and m['seq'] == message['seq']]
    if len(prepare_msg_list) > 2/3 * (len(blockchain.nodes)-1):
        prepare_certificate = True   # "prepared the request" 상태로 변환
        # for문을 비동기로 처리
        threads = []
        for node in blockchain.nodes:
            commit_thread = Thread(target=send, args=(node, {
                'type': 'COMMIT',
                'view': view+2,
                'seq': message['seq'],
                # 'digest': message['digest'],
                'node_id': node_id
            }))
            threads.append(commit_thread)
            commit_thread.start()
        # # 모든 스레드의 종료를 기다림
        # for thread in threads:
        #     thread.join()
    else:
        return jsonify({'message': 'Failed prepare step!'}), 400
    return jsonify({'message': 'Successed prepare step'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    print("~~COMMIT~~")  # Debugging
    global request_data, log, commit_certificate
    message = request.get_json()
    wait_msg('commit')  # 모든 노드한테서 메세지를 받을 때까지 기다리기
    commit_msg_list = [m for m in log if m['type'] == 'COMMIT' and m['view']
                       == message['view'] and m['seq'] == message['seq']]
    if len(commit_msg_list) > 2/3 * len(blockchain.nodes):
        commit_certificate = True   # "commit certificate" 상태로 변환
    # Prepare Certificate & Commit Certificate 상태가 되었다면 블록 추가 시행
    if prepare_certificate and commit_certificate:
        if reply_request():
            return jsonify({'message': 'Successed commit step!'}), 200
    return jsonify({'message': 'Failed commit step!'}), 400


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
    print(client_request)  # Debugging
    # prepare 함수가 수행될 수 있게 설정
    if request_data:
        prepare_event.set()
    # print('Transcaion/new) is_set(): ', end='')  # Debugging
    # print(prepare_event.is_set())  # Debugging
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
    # print('Main) is_set(): ', end='')  # Debugging
    # print(prepare_event.is_set())  # Debugging
    app.run(host='0.0.0.0', port=80)
