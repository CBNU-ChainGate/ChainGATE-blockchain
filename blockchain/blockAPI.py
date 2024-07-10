from flask import Flask, jsonify, request
from threading import Thread
import requests
import socket
import time
from blockchain import Blockchain
from cert import Cert
from config import PORT

app = Flask(__name__)

# Get local IP address
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
consensus_done = [1, 0, 0]
get_pre_msg = 0
get_commit_msg = 0
prepare_certificate = False
commit_certificate = False
start_time = time.time()
consensus_nums = 0
TIMEOUT = 10
stop_pbft = False

blockchain.add_node(node_id)  # Add self IP to nodes


def reset_consensus_state():
    global consensus_nums, log, consensus_done, get_pre_msg, get_commit_msg
    consensus_nums = 0
    log = []
    consensus_done = [1, 0, 0]
    get_pre_msg = 0
    get_commit_msg = 0


def changing_primary():
    """Change Primary node."""
    global primary_N, primary
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
    global consensus_nums
    if consensus_nums > 3:  # Maximum allowed consensus attempts
        consensus_nums = 0
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
    print(response.json())  # Debugging


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
    """Validate pre-prepare message."""
    global request_data, view
    time.sleep(0.5)  # Wait for /transaction/new request

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
    """Request Step."""
    global request_data, view, node_id, primary, start_time
    print("==========Request==========")  # Debugging
    request_data = None
    try:
        message = request.get_json()
        request_data = message['data']  # Store original client request message
        blockchain.len = blockchain.get_block_total()
        if node_id == primary:
            print('Debugging: Pass the IF in Request')  # Debugging
            start_time = time.time()
            N = blockchain.len + 1

            D_m = {"date": message['data']["date"],
                   "time": message['data']["time"]}
            threads = []
            for node in blockchain.nodes:
                if node != node_id:
                    preprepare_thread = Thread(target=send, args=(node, {
                        'type': 'PREPREPARE',
                        'view': view,
                        'seq': N,
                        'digest': D_m,
                    }))
                    threads.append(preprepare_thread)
                    preprepare_thread.start()
            for thread in threads:
                thread.join()
        else:
            return jsonify({'message': '(Request) This is not Primary node!'}), 400
    except Exception as e:
        primary_change_protocol()
        return jsonify({'error': str(e)}), 500
    return jsonify({'message': '(Request) The Request step is complete.'}), 200


@app.route('/consensus/preprepare', methods=['POST'])
def handle_preprepare():
    """Pre-Prepare Step."""
    global consensus_done
    print("==========Pre-prepare==========")  # Debugging
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    message = request.get_json()
    try:
        if validate_preprepare(message):
            print('Debugging: Pass the IF in preprepare!!')  # Debugging
            log.append(message)
            threads = []
            for node in blockchain.nodes:
                if node != node_id:
                    prepare_thread = Thread(target=send, args=(node, {
                        'type': 'PREPARE',
                        'view': view + 1,
                        'seq': message['seq'],
                        'digest': message['digest'],
                        'node_id': node_id
                    }))
                    threads.append(prepare_thread)
                    prepare_thread.start()
            for thread in threads:
                thread.join()
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
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    message = request.get_json()
    while consensus_done[1] != 1 and node_id != primary:
        pass
    try:
        log.append(message)
        if wait_for_messages('prepare'):
            consensus_done[2] += 1
            return jsonify({'message': '(Prepare) Wait the message!'}), 404
        print("==========PREPARE==========")  # Debugging
        prepare_msg_list = [m for m in log if m['type'] == 'PREPARE' and m['view']
                            == message['view'] and m['seq'] == message['seq']]
        if len(prepare_msg_list) > 2 / 3 * (node_len - 1):
            prepare_certificate = True
            threads = []
            for node in blockchain.nodes:
                if node != node_id:
                    commit_thread = Thread(target=send, args=(node, {
                        'type': 'COMMIT',
                        'view': view + 2,
                        'seq': message['seq'],
                        'node_id': node_id
                    }))
                    threads.append(commit_thread)
                    commit_thread.start()
            for thread in threads:
                thread.join()
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
    global request_data, log, commit_certificate, consensus_done, prepare_certificate
    if stop_pbft:
        return jsonify({'error': 'PBFT protocol stopped due to primary change!'}), 500
    while consensus_done[2] < node_len - 1:
        pass
    try:
        message = request.get_json()
        log.append(message)
        if wait_for_messages('commit'):
            return jsonify({'message': '(Commit) Wait the message!'}), 404
        print("==========COMMIT==========")  # Debugging
        commit_msg_list = [m for m in log if m['type'] == 'COMMIT' and m['view']
                           == message['view'] and m['seq'] == message['seq']]
        if len(commit_msg_list) > 2 / 3 * node_len:
            commit_certificate = True

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
    blockchain.add_transaction(request_data)
    last_block = blockchain.last_block
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
    print("Nodes: ", blockchain.nodes)  # Debugging
    print("Primary node: ", primary)  # Debugging
    return jsonify({'message': 'Certificate received successfully.'}), 200


@app.route('/nodes/primary/change', methods=['POST'])
def handle_primary_change():
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
    global request_data, state, primary, node_id, consensus_nums, log, consensus_done

    # Reset state
    reset_consensus_state()

    data = request.get_json()
    # request_data = data  # Store original client request message
    client_request = {'type': 'REQUEST', 'data': data}
    print(client_request)  # Debugging
    send(node_id, client_request)
    return jsonify({'message': 'Send Request to node...'}), 201


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)
