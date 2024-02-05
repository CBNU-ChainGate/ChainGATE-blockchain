from flask import Flask, jsonify, request
from blockchain import Blockchain


app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
entrylog = Blockchain()


def makeEntryLog(data):
    # 데이터를 제외한 블록구조 생성
    previous_block = entrylog.get_previous_block()
    previous_proof = previous_block['proof']
    proof = entrylog.proof_of_work(previous_proof)
    previous_hash = entrylog.hash(previous_block)
    block = entrylog.create_block(proof, previous_hash, data)
    return block


@app.route('/makeEntryLog', methods=['POST'])
def mine_block():
    # params = request.get_data()
    data = request.form['fingerprint']
    new_block = makeEntryLog(data)
    responses = {
        'message': 'Congratulations, you just mined a block!',
        **new_block
    }
    return jsonify(responses), 200


@app.route('/get_chain', methods=['POST'])
def get_chain():
    chaintype = request.form['type']
    print(chaintype)
    if chaintype == '1':
        response = {
            'chain': entrylog.chain,
            'length': len(entrylog.chain)
        }
    elif chaintype == '2':
        pass
    else:
        response = {
            'error': 'User ERROR: wrong type!'
        }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
