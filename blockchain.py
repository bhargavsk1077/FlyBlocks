from hashlib import sha256
import json
import time

from flask import Flask,request
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from block_config import Config


class Block:
    def __init__(self,index,transactions,timestamp,previous_hash,nonce=0):
        self.index=index
        self.transactions=transactions
        self.timestamp=timestamp
        self.previous_hash=previous_hash
        self.nonce = nonce

    def compute_hash(self):
        block_str = json.dumps(self.__dict__,sort_keys=True)
        return sha256(block_str.encode()).hexdigest()

class Blockchain:
    difficulty = 2

    def __init__(self):
        self.chain=[]
        #self.create_genesis()
        self.unconfirmed_transactions=[]

    def create_genesis(self):
        genesis = Block(0,[],0,"0")
        genesis.hash= genesis.compute_hash()
        self.chain.append(genesis)
    
    def new_transaction(self,transaction):
        self.unconfirmed_transactions.append(transaction)

    def mine(self):
        if not self.unconfirmed_transactions:
            return False
        
        last_block = self.last_block
        new_block = Block(index=last_block.index+1,transactions=self.unconfirmed_transactions,timestamp=time.time(),previous_hash=last_block.hash)
        proof=self.proof_work(new_block)
        self.add_block(new_block,proof)
        self.unconfirmed_transactions=[]
        return new_block.index


    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def proof_work(block):
        block.nonce = 0

        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0'*Blockchain.difficulty):
            block.nonce+=1
            computed_hash=block.compute_hash()
        return computed_hash

    def add_block(self, block, proof):
        """
        A function that adds the block to the chain after verification.
        Verification includes:
        * Checking if the proof is valid.
        * The previous_hash referred in the block and the hash of a latest block
          in the chain match.
        """
        previous_hash = self.last_block.hash

        if previous_hash != block.previous_hash:
            #print("hash did not match")
            #print(previous_hash)
            #print(block.previous_hash)
            return False

        if not Blockchain.is_valid_proof(block, proof):
            #print("is valid proof failed")
            return False

        block.hash = proof
        self.chain.append(block)
        return True

    @classmethod
    def is_valid_proof(self, block, block_hash):
        """
        Check if block_hash is valid hash of block and satisfies
        the difficulty criteria.
        """
        return (block_hash.startswith('0' * Blockchain.difficulty) and
                block_hash == block.compute_hash())

    @classmethod
    def check_chain_validity(self,chain):
        result = True
        previous_hash= "0"

        for block in chain:
            block_hash = block.hash
            delattr(block,"hash")

            if not self.is_valid_proof(block,block_hash) or \
                    previous_hash != block.previous_hash:
                        result=False
                        break
            block.hash,previous_hash = block_hash,block_hash

        return result 


app=Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
migrate = Migrate(app,db)

#import transaction_model
#from transaction_model import Blocks

blockchain = Blockchain()
blockchain.create_genesis()
peers = set()

@app.route("/new_transaction",methods=['POST'])
def new_transaction():
    data = request.get_json()
    required_fields = ["author","content"]

    for field in required_fields:
        if not data.get(field):
            return "invalid transaction"

    data["timestamp"]=time.time()
    blockchain.new_transaction(data)
    return "SUCCESS",201

@app.route("/chain",methods=['GET'])
def get_chain():
    chain_data=[]
    for block in blockchain.chain:
        chain_data.append(block.__dict__)
    return json.dumps({"length":len(chain_data),"chain":chain_data,"peers":list(peers)})

@app.route("/pending",methods=['GET'])
def get_pending():
    return json.dumps(blockchain.unconfirmed_transactions)

"""
def add_block_to_db(block,proof):
    block_id = block["id"]
    author = block["transactions"][0]["author"]
    content = block["transactions"][0]["content"]
    post_ts = block["transactions"][0]["timestamp"]
    block_ts = block["timestamp"]
    block_ph = block["previous_hash"]
    block_nonce = block["nonce"]
    block_h = proof

    new_block = Blocks(id=block_id,author=author,content=content,post_timestamp=post_ts,block_timestamp=block_ts,previous_hash=block_ph,nonce=block_nonce,block_hash=block_h)
    db.session.add(new_block)
    db.session.commit()
    
def add_chain_to_db(chain_dump):
    #for idx, block_data in enumerate(chain_dump):
        if idx==0:
            continue
        block = Block(block_data["index"],
                      block_data["transactions"],
                      block_data["timestamp"],
                      block_data["previous_hash"],
                      block_data["nonce"])
        proof = block_data['hash'] 
        add_block_to_db(block,proof)
"""
@app.route("/register_node",methods=['POST'])
def register_node():
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "invalid data",400
    
    peers.add(node_address)

    return get_chain()

@app.route("/register_with",methods=["POST"])
def register_with_existing_node():

    node_address=request.get_json()["node_address"]
    if not node_address:
        return "invalid Data",400

    data = {"node_address":request.host_url}
    headers = {"Content-Type":"application/json"}

    response = requests.post(node_address + "/register_node", data=json.dumps(data),headers = headers)

    if response.status_code==200:
        global blockchain
        global peers

        chain_dump = response.json()['chain']
        blockchain = create_chain_from_dump(chain_dump)
        peers.update(response.json()['peers'])
        #add_chain_to_db(chain_dump)
        return "registration complete",200
    else:
        return response.content,response.status_code

def create_chain_from_dump(chain_dump):
    blockchain = Blockchain()
    blockchain.create_genesis()
    for idx, block_data in enumerate(chain_dump):
        if idx==0:
            continue
        block = Block(block_data["index"],
                      block_data["transactions"],
                      block_data["timestamp"],
                      block_data["previous_hash"],
                      block_data["nonce"])
        proof = block_data['hash']
        added = blockchain.add_block(block, proof)
        if not added:
            raise Exception("The chain dump is tampered!!")
        
    return blockchain
 

def consensus():
    global blockchain
    longest_chain = None 
    current_len = len(blockchain.chain)

    for node in peers:
        response = requests.get('{}/chain'.format(node))
        length = respose.json()['length']
        chain = respose.json()['chain']
        if length > current_len and blockchain.check_chain_validity(chain):
            current_len=length
            longest_chain=chain

    if longest_chain:
        blockchain = longest_chain
        return True

    return False


def announce_block(block):
    for peer in peers:
        url = "{}add_block".format(peer)
        headers = {"Content-Type":"application/json"}
        requests.post(url, data=json.dumps(block.__dict__,sort_keys=True),headers=headers)

@app.route("/add_block",methods=['POST'])
def verify_and_add_block():
    block_data = request.get_json()
    block = Block(block_data["index"],
            block_data["transactions"],
            block_data["timestamp"],
            block_data["previous_hash"],
            block_data["nounce"])


    proof = block_data["hash"]
    added = blockchain.add_block(block,proof)

    if not added:
        return "the block was discarded by the node"

    #add_block_to_db(block,proof)
    return "Block added to the chain",201

@app.route("/mine",methods=['GET'])
def mine_unconfirmed_transcations():
    result = blockchain.mine()
    if not result:
        return "no transactions to mine"
    else:
        chain_length = len(blockchain.chain)
        consensus()
        if chain_length == len(blockchain.chain):
            announce_block(blockchain.last_block)
        return "Block #{} has been mined".format(blockchain.last_block.index)

if __name__=='__main__':
    app.run(debug=True,port=8000)
