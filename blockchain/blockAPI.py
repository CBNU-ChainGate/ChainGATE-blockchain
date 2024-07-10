from flask import Flask, jsonify, request
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
import requests
import socket
import time
from blockchain import Blockchain
from cert import Cert
from config import PORT

app = Flask(__name__)

# 로컬 IP 가져오기
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("google.com", 443))
local_ip = sock.getsockname()[0]
node_id = local_ip

blockchain = Blockchain()
cert = Cert()
node_len = 0
primary = ""
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
start_time = time.time()
consensus_nums = 0
TIMEOUT = 10
stop_pbft = False  # PBFT 프로토콜 중단 플래그

lock = Lock()
executor = ThreadPoolExecutor(max_workers=10)

blockchain.add_node(node_id)  # 본인 IP를 노드에 추가

# ==========================================================================================
# This program is Blockchain API for [ChainGATE] project
# This project is a graduation project from Chungbuk National University.
#
# Date: 2024.07.09
# Writer: Kim Dong Gyu
# Version: 1.0.0
# ==========================================================================================


def changing_primary():
    """Change Primary node."""
    global primary_N, primary, consensus_nums, log, consensus_done, get_pre_msg, get_commit_msg

    with lock:
        # 변수 초기화
        consensus_nums = 0
        log = []
        consensus_done = [1, 0, 0]
        get_pre_msg = 0
        get_commit_msg = 0

        primary_N = (primary_N + 1) % len(blockchain.nodes)
        primary = sorted(blockchain.nodes)[primary_N]
        print(f'Changed Primary Node is "{primary}"')


def primary_change_protocol():
    """Change Primary node protocol."""
    print("==========Primary change Protocol==========")  # debugging
    global primary, request_data, consensus_nums

    with lock:
        # 새로운 뷰 번호와 primary 노드 정보를 모든 노드에게 알림
        message = {
            'type': 'VIEW_CHANGE',
            'new_primary': primary
        }
        for node in blockchain.nodes:
            if node == node_id:
                continue
            response = requests.post(
                f"http://{node}:{PORT}/nodes/primary/change", json=message)
            print(response.json())

        # 새로운 primary 노드 선택
        changing_primary()

        if consensus_nums > 3:  # 한 요청에 대해 허용되는 합의 횟수
            consensus_nums = 0
            print("Error: The maximum number of requests has been exceeded!")
        else:
            # 새로운 primary 노드를 기준으로 합의 과정 재시작
            consensus_nums += 1
            send(primary, {'type': 'REQUEST', 'data': request_data})


def send(receiver, message):
    """API를 통해 각 노드에 요청을 보냄."""
    print(f">>>{message['type']} To {receiver}>>>")
    response = requests.post(
        f"http://{receiver}:{PORT}/consensus/{message['type'].lower()}", json=message)
    print(response.json())  # debugging


def wait_msg(caller):
    """모든 노드의 응답을 받을 때까지 대기."""
    global get_pre_msg, get_commit_msg, node_id, primary
    if caller == 'prepare':
        get_pre_msg += 1  # 응답을 받은 노드 개수 저장
        if node_id == primary and get_pre_msg == node_len:
            get_pre_msg = 0
            print("*****Waiting msg Done*****")
            return False
        elif get_pre_msg == node_len-1:
            get_pre_msg = 0
            print("*****Waiting msg Done*****")
            return False
    elif caller == 'commit':
        get_commit_msg += 1  # 응답을 받은 노드 개수 저장
        if get_commit_msg == node_len:
            get_commit_msg = 0
            print("*****Waiting msg Done*****")
            return False
    return True


def validate_preprepare(preprepare_message):
    """pre-prepare 메세지가 정상적인 메세지인지 검증."""
    global request_data, view
    time.sleep(0.5)  # /transaction/new 요청을 받는데까지의 delay를 기다리기 위함

    # validate_preprepare를 수행하려면 request_data가 필요
    # 따라서 request_data가 설정될 때까지 기다림
    while not request_data:
        print("Waiting client_request (/transaction/new) ...")

    D_m = {
        "date": request_data["date"],
        "time": request_data["time"]
    }
    # client가 보낸 data에 이상이 있다면
    if D_m != preprepare_message['digest']:
        print("validate_preprepare 1단계 실패")
        return False
    # 메세지의 view나 seq의 값에 이상이 있다면
    if preprepare_message['view'] != view or preprepare_message['seq'] != blockchain.len + 1:
        print("validate_preprepare 2단계 실패")
        return False
    return True


########################################################################
### PBFT Protocol (Request > Pre-Prepare > Prepare > Commit > Reply) ###
########################################################################

@app.route('/consensus/request', methods=['POST'])
def handle_request():
    """Requst Step."""
    global view, node_id, primary, start_time
    print("==========Request==========")  # Debugging
    try:
        message = request.get_json()
        blockchain.len = blockchain.get_block_total()
        if node_id == primary:
            print('Debugging: Pass the IF in Request')  # Debugging
            start_time = time.time()  # 제한 시간 재설정
            N = blockchain.len + 1

            # date와 time 값 추출(JSON 형태)
            D_m = {
                "date": message['data']["date"],
                "time": message['data']["time"]
            }
            threads = []
            for node in blockchain.nodes:
                if node == node_id:
                    continue
                preprepare_thread = Thread(target=send, args=(node, {
                    'type': 'PREPREPARE',
                    'view': view,  # 메세지가 전송되는 view
                    'seq': N,  # 요청의 시퀀스 번호
                    'digest': D_m,  # 요청 데이터의 요약본
                }))
                threads.append(preprepare_thread)
                preprepare_thread.start()
        else:
            return jsonify({'message': '(Request) This is not Primary node!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Request) The Request step is complete.'}), 200


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare():  # Primary 노드는 해당 함수 실행 안함
    """Pre-Prepare Step."""
    global consensus_done
    print("==========Pre-prepare==========")  # Debugging
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    message = request.get_json()
    try:
        # pre-prepare 메세지에 대한 검증
        if validate_preprepare(message):
            print('Debugging: Pass the IF in preprepare!!')  # Debugging
            log.append(message)  # pre-prepare 메세지 수집
            # for문을 비동기로 처리
            threads = []
            for node in blockchain.nodes:
                if node == node_id:
                    continue
                prepare_thread = Thread(target=send, args=(node, {
                    'type': 'PREPARE',
                    'view': view + 1,
                    'seq': message['seq'],
                    'digest': message['digest'],
                    'node_id': node_id
                }))
                threads.append(prepare_thread)
                prepare_thread.start()
            consensus_done[1] += 1
        else:
            consensus_done[1] += 1
            return jsonify({'message': '(Pre-prepare) The PRE-PREPARE message is invalid!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Pre-prepare) The Pre-prepare step is complete.'}), 200


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    """Prepare Step."""
    global prepare_certificate, state, start_time, get_pre_msg, log, consensus_done
    print("==========Prepare==========")  # Debugging
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    state = 'PREPARE'
    message = request.get_json()
    try:
        if wait_msg('prepare'):  # 모든 노드에게 prepare 요청이 가기 전까지 대기
            print('Debugging: Pass the IF in Prepare!!')  # Debugging
            log.append(message)  # prepare 메세지 수집
            prepare_certificate = True  # prepare 인증서 생성
            start_time = time.time()  # 제한 시간 재설정
            # for문을 비동기로 처리
            threads = []
            for node in blockchain.nodes:
                if node == node_id:
                    continue
                commit_thread = Thread(target=send, args=(node, {
                    'type': 'COMMIT',
                    'view': view,
                    'seq': message['seq'],
                    'digest': message['digest'],
                    'node_id': node_id
                }))
                threads.append(commit_thread)
                commit_thread.start()
            consensus_done[2] += 1
        else:
            consensus_done[2] += 1
            return jsonify({'message': '(Prepare) The Prepare message is invalid!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Prepare) The Prepare step is complete.'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    """Commit Step."""
    global commit_certificate, get_commit_msg, state
    print("==========Commit==========")  # Debugging
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    state = 'COMMIT'
    message = request.get_json()
    try:
        if wait_msg('commit'):
            print('Debugging: Pass the IF in Commit!!')  # Debugging
            log.append(message)  # commit 메세지 수집
            commit_certificate = True  # commit 인증서 생성
            return jsonify({'message': '(Commit) The Commit message is invalid!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Commit) The Commit step is complete.'}), 200


@app.route('/consensus/reply', methods=['POST'])
def handle_reply():
    """Reply Step."""
    global prepare_certificate, commit_certificate, log, state
    print("==========Reply==========")  # Debugging
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    message = request.get_json()
    try:
        # 상태검증 및 합의 단계 수행 검증
        if prepare_certificate and commit_certificate:
            state = 'REPLY'
            log.append(message)  # reply 메세지 수집
            return jsonify({'message': 'The PBFT protocol is done successfully!!'})
        else:
            return jsonify({'message': '(Reply) The reply message is invalid!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    finally:
        prepare_certificate = False
        commit_certificate = False
        state = 'IDLE'


# transaction이 일어나는 endpoint
@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    global request_data, node_len, state, view, primary, consensus_done, get_pre_msg, get_commit_msg, stop_pbft

    with lock:
        request_data = request.get_json()
        node_len = len(blockchain.nodes)
        state = 'PREPREPARE'
        view = 0
        primary = sorted(blockchain.nodes)[primary_N]
        consensus_done = [1, 0, 0]
        get_pre_msg = 0
        get_commit_msg = 0
        stop_pbft = False

    # 비동기로 PBFT 합의 과정 시작
    executor.submit(pbft_protocol)

    return jsonify({'message': 'New transaction request is created.'}), 200


def pbft_protocol():
    global primary, request_data
    try:
        send(primary, {'type': 'REQUEST', 'data': request_data})
    except Exception as e:
        primary_change_protocol()
        print(f'Error during PBFT protocol: {str(e)}')


# 노드를 추가할 endpoint
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


# primary 변경 protocol
@app.route('/nodes/primary/change', methods=['POST'])
def change_primary():
    values = request.get_json()
    new_primary = values.get('new_primary')
    global primary
    if new_primary:
        primary = new_primary
        return jsonify({'message': f'Primary node changed to {primary}'}), 200
    else:
        return jsonify({'error': 'New primary node not provided!'}), 400


# 현재 노드 리스트를 보여주는 endpoint
@app.route('/nodes/list', methods=['GET'])
def list_nodes():
    response = {
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 200


# 노드 리스트를 삭제하는 endpoint
@app.route('/nodes/clear', methods=['POST'])
def clear_nodes():
    blockchain.nodes.clear()
    response = {
        'message': 'All nodes have been cleared',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)
