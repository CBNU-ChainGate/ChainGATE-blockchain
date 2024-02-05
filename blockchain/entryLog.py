'''
출입기록에 대한 블록
'''

from blockchain import Blockchain
import datetime


class EntryLog(Blockchain):
    def create_block(self, proof, previous_hash, data):
        block = {'index': len(self.chain) + 1,
                 'timestamp': str(datetime.datetime.now()),
                 'data': data,  # json 형태의 데이터
                 'proof': proof,
                 'previous_hash': previous_hash}
        self.chain.append(block)
        return block
