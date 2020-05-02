from hashlib import sha256
import json
import time
from datetime import datetime
from flask import Flask,request
import requests
from flask_migrate import Migrate
from block_config import Config



app=Flask(__name__)
app.config.from_object(Config)


import transaction_model
from transaction_model import Block,Transaction,Blockchain,Peers,db
db.init_app(app)
migrate = Migrate(app,db)

def return_peers():
    list1 = Peers.query.all()
    p=[]
    for peer in list1:
        p.append(peer.address)
    return p


def consensus():
    global blockchain
    longest_chain = None 
    current_len = len(blockchain.chain)

    for node in peers:
        try:
            response = requests.get('{}chain'.format(node))
            length = response.json()['length']
            chain = response.json()['chain']
            if length > current_len and blockchain.check_chain_validity(chain):
                current_len=length
                longest_chain=chain
            #print("try in consensus passed")
        except Exception as e:
            print(e)


    if longest_chain:
        blockchain = create_chain_from_dump(longest_chain)
        return True

    return False

def create_chain_from_dump(chain_dump):
    #print("creating chain from dump")
    Block.query.delete()
    Transaction.query.delete()
    db.session.commit()
    blockchain = Blockchain()
    blockchain.create_genesis()
    for idx, block_data in enumerate(chain_dump):
        if idx==0:
            continue
        block = Block(block_data["id"],
                      block_data["previous_hash"],
                      datetime.fromtimestamp(block_data["block_timestamp"]),
                      block_data["nonce"])
        proof = block_data['block_hash']
        #===========================================
        db.session.add(block)
        db.session.commit()

        new_block=Block.query.get(blockchain.last_block["id"]+1)
        new_block.add_tx(block_data["transactions"])
        db.session.commit()
        #=========================================
        added = blockchain.add_block(new_block.id, proof)
        if not added:
            raise Exception("The chain dump is tampered!!")
    #print("created chain from dump succesfully")
    return blockchain

with app.app_context():
    try:
        blockchain = Blockchain()
        if not blockchain.chain:
            blockchain.create_genesis()
         
        peers = set(return_peers())
        #print(peers)
        #print("starting consensus")
        consensus()
    except Exception as e:
        print(e)
        pass


@app.shell_context_processor
def make_shell_context():
    return {'db':db,'Block':Block,'Transaction':Transaction,'Peers':Peers,'Blockchain':Blockchain}

@app.route("/new_transaction",methods=['POST'])
def new_transaction():
    data = request.get_json()
    required_fields = ["author","content"]

    for field in required_fields:
        if not data.get(field):
            return "invalid transaction"

    data["timestamp"]=datetime.utcnow().timestamp()
    blockchain.new_transaction(data)
    return "SUCCESS",201

@app.route("/chain",methods=['GET'])
def get_chain():
    chain_data=blockchain.chain 
    return json.dumps({"length":len(chain_data),"chain":chain_data,"peers":list(peers)})

@app.route("/pending",methods=['GET'])
def get_pending():
    return json.dumps(blockchain.unconfirmed_transactions)



@app.route("/register_node",methods=['POST'])
def register_node():
    global peers
    node_address = request.get_json()["node_address"]
    if not node_address:
        return "invalid data",400
    if not Peers.query.filter_by(address=node_address).all():    
        peer=Peers(address=node_address)
        db.session.add(peer)
        db.session.commit()
    peers = set(return_peers())
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
        ps = response.json()['peers']
        for p in ps:
            if p not in peers and p!=request.host_url:
                peer = Peers(address=p)
                db.session.add(peer)
                db.session.commit()

        peer = Peers(address=node_address+"/")
        db.session.add(peer)
        db.session.commit()
        peers = set(return_peers())
        return "registration complete",200
    else:
        return response.content,response.status_code


def announce_block(block):
    for peer in peers:
        try:
            url = "{}add_block".format(peer)
            headers = {"Content-Type":"application/json"}
            requests.post(url, data=json.dumps(block,sort_keys=True),headers=headers)
        except:
            pass

@app.route("/add_block",methods=['POST'])
def verify_and_add_block():
    block_data = request.get_json()
    block = Block(block_data["id"],
            block_data["previous_hash"],
            datetime.fromtimestamp(block_data["block_timestamp"]),
            block_data["nonce"])


    proof = block_data["block_hash"]
    #===========================================
    db.session.add(block)
    db.session.commit()

    new_block=Block.query.get(blockchain.last_block["id"]+1)
    new_block.add_tx(block_data["transactions"])
    db.session.commit()
    #=========================================

    added = blockchain.add_block(new_block.id,proof)

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

        return "Block #{} has been mined".format(blockchain.last_block["id"])





if __name__=='__main__':
    
    app.run(debug=True,port=8000)
