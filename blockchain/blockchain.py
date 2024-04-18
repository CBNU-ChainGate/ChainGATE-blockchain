import hashlib
import json
import time
from urllib.parse import urlparse
import requests

# 블록체인 클래스 정의


class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()

        # genesis 블록 생성
        self.create_block(previous_hash='0')

    # 블록생성
    def create_block(self, previous_hash):
        if self.pending_transactions:
            block = {
                'timestamp': str(time()),
                'previous_hash': previous_hash,
                'transactions': self.pending_transactions
            }
            self.pending_transactions = []
            self.chain.append(block)
            return True
        return False

    # 트랜젝션 추가
    def add_transaction(self, data):
        self.pending_transactions.append(data)

    # 노드 추가
    def add_node(self, node):
        address = urlparse(node)
        self.nodes.add(address.netloc)

    # 노드 간의 블록체인 동기화
    def synchronize_node(self):
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/chain/get')
            if response.status_code == 200:
                chain = response.json()['chain']
                length = response.json()['length']

                # 길이가 더 긴 노드의 데이터로 동기화
                if length > max_length:
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        return False

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def get_lastblock(self):
        if len(self.chain) == 0:
            return 0
        return self.chain[-1]


# # PBFT 노드 클래스 정의
# class PBFTNode:
#     def __init__(self, node_id, blockchain):
#         self.node_id = node_id
#         self.blockchain = blockchain
#         self.state = 'IDLE'
#         self.log = []
#         self.primary = list(self.blockchain.nodes)[
#             0] if self.blockchain.nodes else None
#         self.request_message = None

#     def send(self, receiver, message):
#         receiver.receive(message)

#     def receive(self, message):
#         if message['type'] == 'REQUEST':
#             self.handle_request(message)
#         elif message['type'] == 'PREPREPARE':
#             self.handle_preprepare(message)
#         elif message['type'] == 'PREPARE':
#             self.handle_prepare(message)
#         elif message['type'] == 'COMMIT':
#             self.handle_commit(message)

#     def handle_request(self, message):
#         print("~~REQUEST~~")
#         if self.node_id == self.primary:
#             self.request_message = message  # 원본 클라이언트 요청 메시지 저장
#             N = len(self.blockchain.chain) + 1
#             D_m = hashlib.sha256(json.dumps(message).encode()).hexdigest()
#             preprepare_message = {
#                 'type': 'PREPREPARE',
#                 'view': 0,
#                 'seq': N,  # 요청의 시퀀스 번호
#                 'digest': D_m
#             }
#             for node in self.blockchain.nodes:  # 이 부분 API request로 고치기 #########
#                 self.send(node, preprepare_message)

#     def handle_preprepare(self, message):
#         print("~~PREPREPARE~~")
#         if self.state == 'IDLE':
#             self.state = 'PREPREPARE'
#             self.log.append(message)
#             D_m = hashlib.sha256(json.dumps(message).encode()).hexdigest()
#             prepare_message = {
#                 'type': 'PREPARE',
#                 'view': 1,
#                 'seq': message['seq'],
#                 'digest': D_m,
#                 'node_id': self.node_id
#             }
#             for node in self.blockchain.nodes:  # 이 부분 API request로 고치기 #########
#                 self.send(node, prepare_message)

#     def handle_prepare(self, message):
#         print("~~PREPARE~~")
#         if self.state == 'PREPREPARE':
#             self.log.append(message)
#             if len([m for m in self.log if m['type'] == 'PREPARE' and m['view'] == message['view'] and m['seq'] == message['seq']]) > 2/3 * len(self.blockchain.nodes):
#                 for node in self.blockchain.nodes:
#                     commit_message = {
#                         'type': 'COMMIT',
#                         'view': 2,
#                         'seq': message['seq'],
#                         'node_id': self.node_id
#                     }
#                     # 이 부분 API request로 고치기 #########
#                     self.send(node, commit_message)

#     def handle_commit(self, message):
#         print("~~COMMIT~~")
#         if self.state == 'PREPARE':
#             self.log.append(message)
#             if len([m for m in self.log if m['type'] == 'COMMIT' and m['view'] == message['view'] and m['seq'] == message['seq']]) > 2/3 * len(self.blockchain.nodes):
#                 self.state = 'IDLE'
#                 self.blockchain.add_transaction(self.request_message)
#                 if self.blockchain.create_block(self.blockchain.hash(self.blockchain.get_lastblock())):
#                     print(f"Node [{self.node_id}] committed new block")
#                 else:
#                     print("Error: Failed to commit new block!")
