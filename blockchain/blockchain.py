import hashlib
import json
import time
from urllib.parse import urlparse
import requests
from db_manager import MySQLManager
from config import DB_LOCALHOST, DB_USER, DB_PASS, DB_DATABASE

db_manager = MySQLManager(
    host=DB_LOCALHOST, user=DB_USER, password=DB_PASS, database=DB_DATABASE)
db_manager.connect()

# # 데이터 삽입 예제
# db_manager.execute_query("INSERT INTO example (name) VALUES (%s)", ("Alice",))
# db_manager.execute_query("INSERT INTO example (name) VALUES (%s)", ("Bob",))

# # 데이터 조회 예제
# results = db_manager.fetch_query("SELECT * FROM example")
# for row in results:
#     print(row)


class Blockchain:
    """블록체인 정의"""

    def __init__(self):
        self.chain = []
        self.last_block = {}
        self.pending_transactions = {}
        self.nodes = set()

        # genesis 블록 생성
        self.create_block(previous_hash='0')

    # 블록생성
    def create_block(self, previous_hash):
        if self.pending_transactions:
            block = {
                'timestamp': time.time(),
                'previous_hash': previous_hash,
                # 'transactions': self.pending_transactions,
                "date": self.pending_transactions.get('date'),
                "department": self.pending_transactions.get('department'),
                "name": self.pending_transactions.get('name'),
                "position": self.pending_transactions.get('position'),
                "time": self.pending_transactions.get('time')
            }
            self.pending_transactions = []
            # self.chain.append(block)
            self.last_block = block
            return True
        return False

    # 트랜젝션 추가
    def add_transaction(self, data):
        # self.pending_transactions.append(data)
        self.pending_transactions = data

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

    # def get_lastblock(self):
    #     if len(self.chain) == 0:
    #         return 0
    #     return self.chain[-1]
