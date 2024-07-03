import hashlib
import json
import time
from urllib.parse import urlparse
import requests


class Blockchain:
    """블록체인 정의"""

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
                'timestamp': str(time.time()),
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
        # address = urlparse(node)
        # self.nodes.add(address.netloc)
        self.nodes.add(node)

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
