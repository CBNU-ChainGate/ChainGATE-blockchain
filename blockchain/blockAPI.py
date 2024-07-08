from flask import Flask, jsonify, request
from threading import Thread
import requests
import socket
import time
from blockchain import Blockchain
from cert import Cert

app = Flask(__name__)

# 로컬 IP 가져오기
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("google.com", 443))
local_ip = sock.getsockname()[0]

blockchain = Blockchain()
cert = Cert()
node_len = 0
node_id = local_ip  # 어떻게 처리할지 재고려
port = ""
primary = "192.168.0.28"  # primary 정하는 알고리즘 추가 필요
primary_N = 0
state = 'IDLE'
view = 0
log = []
request_data = None
consensus_done = [1, 0, 0]  # 진행완료 된 합의단계
get_pre_msg = 0  # prepare 요청을 받은 수
get_commit_msg = 0  # commit 요청을 받은 수
prepare_certificate = False
commit_certificate = False
consensus_failed = False
start_time = time.time()
consensus_nums = 0
TIMEOUT = 10

# blockchain.add_node(node_id)  # 본인 IP를 노드에 추가


# ==========================================================================================
# Date: 2024.07.03
# Writer: Kim Dong Gyu
# Version: 1.0.0
# ==========================================================================================

def find_next_primary():
    nodes = list(blockchain.nodes)
    nodes.sort()
    index = nodes.index(primary)
    if index == len(nodes) - 1:
        return nodes[0]
    else:
        return nodes[index + 1]


def primary_change_protocol():
    global view, primary, consensus_failed, start_time, request_data, consensus_nums

    while consensus_failed or (time.time() - start_time) > TIMEOUT:
        consensus_failed = False  # 합의 실패 플래그 초기화
        # 새로운 primary 노드 선택
        primary = find_next_primary()
        # 새로운 뷰 번호와 primary 노드 정보를 모든 노드에게 알림
        message = {
            'type': 'VIEW_CHANGE',
            'new_primary': primary
        }
        for node in blockchain.nodes:
            response = requests.post(
                f"http://{node}/primary/change", json=message)
            print(response)

        if consensus_nums > 4:
            consensus_nums = 0
            print("Error: The maximum number of requests has been exceeded!")
        else:
            # 새로운 primary 노드를 기준으로 합의 과정 재시작
            consensus_nums += 1
            send(primary, {'type': 'REQUEST', 'data': request_data})
    time.sleep(1)


def send(receiver, message):
    """API를 통해 각 노드에 요청을 보냄"""
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
        response = requests.post(
            f"http://{receiver}/consensus/prepare", json=message)

    elif message['type'] == 'COMMIT':
        print("===============COMMIT===============")
        response = requests.post(
            f"http://{receiver}/consensus/commit", json=message)
    print(response.json())  # debugging


def wait_msg(caller):
    """모든 노드의 응답을 받을 때까지 대기"""
    global get_pre_msg, get_commit_msg, node_id, primary
    if caller == 'prepare':
        get_pre_msg += 1     # 응답을 받은 노드 개수 저장
        if node_id == primary and get_pre_msg == node_len:
            get_pre_msg = 0
            print("*****GET ALL MESSAGE*****")
            return False
        elif get_pre_msg == node_len-1:
            get_pre_msg = 0
            print("*****GET ALL MESSAGE*****")
            return False
    elif caller == 'commit':
        get_commit_msg += 1     # 응답을 받은 노드 개수 저장
        if get_commit_msg == node_len:
            get_commit_msg = 0
            print("*****GET ALL MESSAGE*****")
            return False
    return True


def validate_preprepare(preprepare_message):
    """pre-prepare 메세지가 정상적인 메세지인지 검증"""
    global request_data

    # validate_preprepare를 수행하려면 request_data가 필요
    # 따라서 request_data가 설정될 때까지 기다림
    while not request_data:
        print("Waiting client_request ...")

    D_m = {
        "date": request_data["date"],
        "time": request_data["time"]
    }
    # client가 보낸 data에 이상이 있다면
    if D_m != preprepare_message['digest']:
        print("validate_preprepare 1단계 실패")
        return False
    # 메세지의 view나 seq의 값에 이상이 있다면
    if preprepare_message['view'] != view or preprepare_message['seq'] != blockchain.len+1:
        print("validate_preprepare 2단계 실패")
        print(preprepare_message['view'])
        print(view)
        print(preprepare_message['seq'])
        print(blockchain.len+1)
        return False
    return True


@app.route('/consensus/request', methods=['POST'])
def handle_request():
    global view, node_id, primary, start_time, consensus_failed
    print("~~Request~~")  # Debugging
    try:
        message = request.get_json()
        blockchain.len = blockchain.get_block_total()
        if node_id == primary:
            start_time = time.time()  # 제한 시간 재설정
            print('Request > if YES!!')  # Debugging
            N = blockchain.len + 1
            print("len: ", end='')  # debugging
            print(blockchain.len)  # debugging
            # date와 time 값 추출(JSON 형태)
            D_m = {
                "date": message['data']["date"],
                "time": message['data']["time"]
            }
            threads = []
            for node in blockchain.nodes:
                preprepare_thread = Thread(target=send, args=(node, {
                    'type': 'PREPREPARE',
                    'view': view,   # 메세지가 전송되는 view
                    'seq': N,       # 요청의 시퀀스 번호
                    'digest': D_m,   # 요청 데이터의 요약본
                }))
                threads.append(preprepare_thread)
                preprepare_thread.start()
        else:
            return jsonify({'message': '~Not Primary node~'}), 400
    except Exception as e:
        consensus_failed = True
        return jsonify({'message': str(e)}), 500
    return jsonify({'message': 'Pre-prepare message sended'}), 200


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare():  # Primary 노드는 해당 함수 실행 안함
    global consensus_failed, consensus_done
    print("~~Pre-prepare~~")  # Debugging
    message = request.get_json()
    try:
        # pre-prepare 메세지에 대한 검증
        if validate_preprepare(message):  # 검증방법 재고려 필요 OOOOOOOOOOOOOOO
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
            consensus_done[1] += 1
        else:
            consensus_done[1] += 1
            return jsonify({'message': 'Invalid PRE-PREPARE message!'}), 400
    except Exception as e:
        consensus_failed = True
        return jsonify({'message': str(e)}), 500
    return jsonify({'message': 'Pre-prepare message validated'}), 200


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    global prepare_certificate, log, consensus_failed, consensus_done
    message = request.get_json()
    while consensus_done[1] != 1 and node_id != primary:
        pass
    try:
        log.append(message)         # prepare 메세지 수집
        if wait_msg('prepare'):  # 모든 노드한테서 메세지를 받을 때까지 기다리기
            consensus_done[2] += 1
            return jsonify({'message': 'Wait the message!'}), 404
        print("~~PREPARE~~")  # Debugging
        prepare_msg_list = [m for m in log if m['type'] == 'PREPARE' and m['view']
                            == message['view'] and m['seq'] == message['seq']]
        if len(prepare_msg_list) > 2/3 * (node_len-1):
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
            consensus_done[2] += 1
        else:
            consensus_done[2] += 1
            return jsonify({'message': 'Failed prepare step!'}), 400
    except Exception as e:
        consensus_failed = True
        return jsonify({'message': str(e)}), 500
    return jsonify({'message': 'Successed prepare step'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    global request_data, log, commit_certificate, consensus_failed, consensus_done
    while consensus_done[2] < node_len-1:
        pass
    try:
        message = request.get_json()
        log.append(message)         # commit 메세지 수집
        if wait_msg('commit'):  # 모든 노드한테서 메세지를 받을 때까지 기다리기
            return jsonify({'message': 'Wait the message!'}), 404
        print("~~COMMIT~~")  # Debugging
        commit_msg_list = [m for m in log if m['type'] == 'COMMIT' and m['view']
                           == message['view'] and m['seq'] == message['seq']]
        if len(commit_msg_list) > 2/3 * node_len:
            commit_certificate = True   # "commit certificate" 상태로 변환
        # Prepare Certificate & Commit Certificate 상태가 되었다면 블록 추가 시행
        if prepare_certificate and commit_certificate:
            if reply_request():
                log = []
                consensus_done = [1, 0, 0]
                return jsonify({'message': 'Successed commit step!'}), 200
    except Exception as e:
        consensus_failed = True
        return jsonify({'message': str(e)}), 500
    return jsonify({'message': 'Failed commit step!'}), 400


def reply_request():
    blockchain.add_transaction(request_data)
    last_block = blockchain.last_block
    if blockchain.create_block(blockchain.hash(last_block)):
        print(f"** Node [{node_id}] added a new block **")
        return True
    return False


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    global node_len, primary, primary_N
    cert_pem = request.json.get('cert')
    if not cert_pem:
        return jsonify({'error': 'No certificate data provided'}), 400

    if cert.verify_cert(cert_pem):
        node = request.remote_addr
        blockchain.add_node(node)
    node_len = len(blockchain.nodes)

    nodes = sorted(blockchain.nodes)
    primary = nodes[primary_N]
    print("Nodes: ", end='')  # debugging
    print(blockchain.nodes)  # debugging
    print("Primary node: ", end='')  # debugging
    print(primary)  # debugging
    return jsonify({'message': 'Certificate received successfully'}), 200


@app.route('/chain/search', methods=['POST'])
def search_chain():
    data = request.get_json()
    results = blockchain.search_block(
        data['date'], data['name'], data['department'])
    if not results:
        return jsonify({'error': 'No matching records found'}), 404
    return jsonify({'results': results}), 200


@app.route('/chain/get', methods=['GET'])
def full_chain():
    result = blockchain.get_block_total()
    return jsonify(result), 200


@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    """register nodes"""
    global request_data, state, primary, node_id, port
    data = request.get_json()
    state = 'REQUEST'
    request_data = data  # 원본 클라이언트 요청 메시지 저장
    client_request = {
        'type': 'REQUEST',
        'data': data
    }
    print(client_request)  # Debugging
    send(node_id+port, client_request)
    return jsonify({'message': 'Send Request to node...'}), 201


@app.route('/primary/change', methods=['POST'])
def primary_change():
    global primary, log
    message = request.get_json()
    if message['type'] == 'VIEW_CHANGE':
        primary = message['new_primary']
        log = []
        return jsonify({'message': 'View changed successfully'}), 200
    return jsonify({'message': 'Wrong Message!'}), 400


if __name__ == "__main__":
    # view_change_thread = Thread(target=primary_change_protocol)
    # view_change_thread.start()
    app.run(host='0.0.0.0', port=80)
