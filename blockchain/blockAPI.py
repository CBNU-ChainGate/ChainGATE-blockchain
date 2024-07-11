from flask import Flask, jsonify, request
from threading import Thread
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
sock.close()

node_id = local_ip
blockchain = Blockchain()
cert = Cert()

# Initial values for PBFT state variables
node_len = 0
primary = ""
primary_N = 0
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
pbft_protocol_condition = False

blockchain.add_node(node_id)  # 본인 IP를 노드에 추가

# ==========================================================================================
# This program is Blockchain API for [ChainGATE] project
# This project is a graduation project from Chungbuk National University.
#
# Date: 2024.07.09
# Writer: Kim Dong Gyu
# Version: 1.0.0
# ==========================================================================================


def reset_consensus_state():
    global consensus_nums, log, consensus_done, get_pre_msg, get_commit_msg
    consensus_nums = 0
    log = []
    consensus_done = [1, 0, 0]
    get_pre_msg = 0
    get_commit_msg = 0


def changing_primary():
    """Change Primary node."""
    global primary_N, primary, pbft_protocol_condition
    reset_consensus_state()
    primary_N = (primary_N + 1) % len(blockchain.nodes)
    primary = sorted(blockchain.nodes)[primary_N]
    print(f'Changed Primary Node is "{primary}"')


def notify_primary_change():
    """Notify all nodes about the new primary."""
    message = {'type': 'VIEW_CHANGE', 'new_primary': primary}
    for node in blockchain.nodes:
        if node != node_id:
            response = requests.post(
                f"http://{node}:{PORT}/nodes/primary/change", json=message)
            print(response.json())


def primary_change_protocol():
    """Change Primary node protocol."""
    print("==========Primary change Protocol==========")  # Debugging
    notify_primary_change()
    changing_primary()
    global consensus_nums, pbft_protocol_condition
    if consensus_nums > 3:  # Maximum allowed consensus attempts
        consensus_nums = 0
        pbft_protocol_condition = False  # PBFT 프로토콜이 중단됨을 알림
        print("Error: The maximum number of requests has been exceeded!")
    else:
        consensus_nums += 1
        send(primary, {'type': 'REQUEST', 'data': request_data})


def send(receiver, message):
    """Send API request to nodes."""
    endpoint = {
        'REQUEST': '/consensus/request',
        'PREPREPARE': '/consensus/preprepare',
        'PREPARE': '/consensus/prepare',
        'COMMIT': '/consensus/commit'
    }[message['type']]
    print(f">>>{message['type']} To {receiver}>>>")
    response = requests.post(
        f"http://{receiver}:{PORT}{endpoint}", json=message)
    # print(response.json())  # Debugging


def wait_for_messages(caller):
    """Wait for responses from all nodes."""
    global get_pre_msg, get_commit_msg, node_id, primary, node_len
    if caller == 'prepare':
        get_pre_msg += 1
        if (node_id == primary and get_pre_msg == node_len) or get_pre_msg == node_len - 1:
            get_pre_msg = 0
            print("*****Waiting msg Done*****")
            return False
    elif caller == 'commit':
        get_commit_msg += 1
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

    D_m = {"date": request_data["date"], "time": request_data["time"]}
    if D_m != preprepare_message['digest']:
        print("validate_preprepare 1단계 실패")
        return False
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
            # print('Debugging: Pass the IF in Request')  # Debugging
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
                    'view': view,   # 메세지가 전송되는 view
                    'seq': N,       # 요청의 시퀀스 번호
                    'digest': D_m,   # 요청 데이터의 요약본
                }))
                threads.append(preprepare_thread)
                preprepare_thread.start()
        else:
            print("This is not Primary node!")  # Debugging
            return jsonify({'message': f'(Request) not Primary node.'}), 400
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
        print("PBFT Protocol stopedd due to primary change!")  # Debugging
        return jsonify({'error': 'PBFT protocol has stopped.'}), 500
    message = request.get_json()
    try:
        # pre-prepare 메세지에 대한 검증
        if validate_preprepare(message):
            # print('Debugging: Pass the IF in preprepare!!')  # Debugging
            log.append(message)  # pre-prepare 메세지 수집
            # for문을 비동기로 처리
            threads = []
            for node in blockchain.nodes:
                if node == node_id:
                    continue
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
            return jsonify({'message': '(Pre-prepare) The PRE-PREPARE message is invalid!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Pre-prepare) The Pre-prepare step is complete.'}), 200


@app.route('/consensus/prepare', methods=['POST'])
def handle_prepare():
    """Prepare Step."""
    global prepare_certificate, log, consensus_done, get_pre_msg
    if stop_pbft:
        print("PBFT Protocol stopedd due to primary change!")  # Debugging
        return jsonify({'error': 'PBFT protocol has stopped.'}), 500
    message = request.get_json()
    while consensus_done[1] != 1 and node_id != primary:
        pass
    try:
        log.append(message)         # prepare 메세지 수집
        if wait_for_messages('prepare'):  # 모든 노드한테서 메세지를 받을 때까지 기다리기
            consensus_done[2] += 1
            return jsonify({'message': '(Prepare) Waiting the message.'}), 404
        print("==========PREPARE==========")  # Debugging
        prepare_msg_list = [m for m in log if m['type'] == 'PREPARE' and m['view']
                            == message['view'] and m['seq'] == message['seq']]
        if len(prepare_msg_list) > 2/3 * (node_len-1):
            prepare_certificate = True   # "prepared the request" 상태로 변환
            # for문을 비동기로 처리
            threads = []
            for node in blockchain.nodes:
                if node == node_id:
                    continue
                commit_thread = Thread(target=send, args=(node, {
                    'type': 'COMMIT',
                    'view': view+2,
                    'seq': message['seq'],
                    'node_id': node_id
                }))
                threads.append(commit_thread)
                commit_thread.start()
            consensus_done[2] += 1
        else:
            consensus_done[2] += 1
            return jsonify({'message': '(Prepare) The Prepare step is failed!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Prepare) The Prepare step is complete.'}), 200


@app.route('/consensus/commit', methods=['POST'])
def handle_commit():
    """Commit Step."""
    global request_data, log, commit_certificate, consensus_done, prepare_certificate, commit_certificate
    if stop_pbft:
        print("PBFT Protocol stopedd due to primary change!")  # Debugging
        return jsonify({'error': 'PBFT protocol has stopped.'}), 500
    while consensus_done[2] < node_len-1:
        pass
    try:
        message = request.get_json()
        log.append(message)         # commit 메세지 수집
        if wait_for_messages('commit'):  # 모든 노드한테서 메세지를 받을 때까지 기다리기
            return jsonify({'message': '(Commit) Waiting the message.'}), 404
        print("==========COMMIT==========")  # Debugging
        commit_msg_list = [m for m in log if m['type'] == 'COMMIT' and m['view']
                           == message['view'] and m['seq'] == message['seq']]
        if len(commit_msg_list) > 2/3 * node_len:
            commit_certificate = True   # "commit certificate" 상태로 변환

        # Prepare Certificate & Commit Certificate 상태가 되었다면 블록 추가 시행
        if prepare_certificate and commit_certificate:
            prepare_certificate = False
            commit_certificate = False
            if reply_request():
                return jsonify({'message': '(Commit) The Commit step is complete.'}), 200
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Commit) The commit step is failed!'}), 400


def reply_request():
    """Reply to blockchain."""
    global pbft_protocol_condition
    blockchain.add_transaction(request_data)
    last_block = blockchain.last_block
    pbft_protocol_condition = False  # PBFT 프로토콜이 끝났음을 알림

    if blockchain.create_block(blockchain.hash(last_block)):
        print(f"** Node [{node_id}] added a new block **")
        return True
    return False

########################################################################
### PBFT Protocol (End)                                              ###
########################################################################


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    """Register nodes participating in consensus."""
    global node_len, primary
    cert_pem = request.json.get('cert')
    if not cert_pem:
        return jsonify({'message': 'No certificate data provided!'}), 400

    if cert.verify_cert(cert_pem):
        node = request.remote_addr
        blockchain.add_node(node)
    else:
        return jsonify({'message': 'Invalid or disallowed certificate!'}), 400

    node_len = len(blockchain.nodes) - 1

    nodes = sorted(blockchain.nodes)
    primary = nodes[primary_N]
    # print("Nodes: ", end='')  # debugging
    # print(blockchain.nodes)  # debugging
    # print("Primary node: ", end='')  # debugging
    # print(primary)  # debugging
    return jsonify({'message': 'Certificate received successfully.'}), 200


@app.route('/nodes/primary/change', methods=['POST'])
def handel_primary_change():
    """Change primary nodes."""
    global primary, log, stop_pbft
    message = request.get_json()
    if message['type'] == 'VIEW_CHANGE':
        stop_pbft = True
        primary = message['new_primary']
        log = []
        changing_primary()
        time.sleep(2)
        stop_pbft = False
        return jsonify({'message': 'View changed successfully.'}), 200
    return jsonify({'message': 'Wrong Message!'}), 400


@app.route('/chain/search', methods=['POST'])
def search_chain():
    """Search data from blockchain."""
    data = request.get_json()
    results = blockchain.search_block(
        data['date'], data['name'], data['department'])
    if not results:
        return jsonify({'error': 'No matching records found!'}), 404
    return jsonify({'results': results}), 200


@app.route('/chain/get', methods=['GET'])
def full_chain():
    """Get data count from blockchain."""
    result = blockchain.get_block_total()
    return jsonify(result), 200


@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    """Issue transaction and execute consensus protocol for block creation."""
    global pbft_protocol_condition, request_data, state, primary, node_id, consensus_nums, log, consensus_done

    while pbft_protocol_condition:
        pass

    # 변수 초기화
    reset_consensus_state()
    request_data = None

    data = request.get_json()
    state = 'REQUEST'
    request_data = data  # 원본 클라이언트 요청 메시지 저장
    client_request = {
        'type': 'REQUEST',
        'data': data
    }
    # print(client_request)  # Debugging
    pbft_protocol_condition = True  # PBFT 프로토콜이 수행 중임을 알림
    send(node_id, client_request)
    return jsonify({'message': 'Send Request to node...'}), 201


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
