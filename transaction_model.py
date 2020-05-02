
from hashlib import sha256
import json
import time
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Block(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    transactions = db.relationship('Transaction',backref='parent_block',lazy='dynamic')
    block_timestamp = db.Column(db.DateTime,default = datetime.utcnow)
    previous_hash = db.Column(db.String(64))
    nonce = db.Column(db.Integer,default=0)
    block_hash = db.Column(db.String(64))

    def __init__(self,id,previous_hash,timestamp=datetime.utcnow(),nonce=0):
        super().__init__(id=id,previous_hash=previous_hash,block_timestamp=timestamp,nonce=nonce)
        self.id = id
        self.block_timestamp=timestamp
        self.previous_hash=previous_hash
        self.nonce = nonce

    def __repr__(self):
        return "<block {}>".format(self.id)

    def compute_hash(self):
        dict1= self.__dict__
        keys = list(dict1.keys())
        dictionary=dict() 
        for key in keys:
            if key in ["id","transactions","previous_hash","nonce"]:
                dictionary[key] = dict1[key]

        transactions=[]
        txs=self.transactions.all()
        for tx in txs:
            t={'author':tx.author,'content':tx.content}
            tsp=tx.post_timestamp
            if isinstance(tsp,datetime):
                t['post_timestamp']=tsp.timestamp()
            transactions.append(t)
            
        dictionary['transactions']=transactions 
        
        ts=self.block_timestamp
        if isinstance(ts,datetime):
            dictionary['block_timestamp']=ts.timestamp()


        block_str = json.dumps(dictionary,sort_keys=True)
        return sha256(block_str.encode()).hexdigest()
    
    def set_hash(self,hash_str):
        self.block_hash=hash_str

    def add_tx(self,tx_list):
        for t in tx_list:
            author = t["author"]
            content = t["content"]
            try:
                post_timestamp=datetime.fromtimestamp(t["post_timestamp"])
                tx = Transaction(block_id=self.id,author=author,content=content,post_timestamp=post_timestamp)
            except:
                tx = Transaction(block_id=self.id,author=author,content=content)
            db.session.add(tx)
        #db.session.commit()



class Transaction(db.Model):

    id = db.Column(db.Integer,primary_key=True)
    block_id = db.Column(db.Integer,db.ForeignKey('block.id'))
    author = db.Column(db.String(64))
    content = db.Column(db.String(140))
    post_timestamp = db.Column(db.DateTime,default = datetime.utcnow)

    def __repr__(self):
        return "<tx {}>".format(self.content)

class Peers(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    address = db.Column(db.String(100))
    
    def __repr__(self):
        return "<address {}>".format(self.address)

class Blockchain:
    difficulty = 2

    def __init__(self):
        self.chain=self.return_chain() 
        self.unconfirmed_transactions=[]

    @staticmethod
    def return_chain():
        chain=[]
        block_list = Block.query.all()
        for block in block_list:
            transactions = []        
            txs = Transaction.query.filter_by(block_id=block.id).all()
            for tx in txs:
                t={'author':tx.author,'content':tx.content}
                ts = tx.post_timestamp
                if isinstance(ts,datetime):
                    t['post_timestamp']=ts.timestamp()
                transactions.append(t)
            b={"id":block.id,
                    "previous_hash":block.previous_hash, 
                    "nonce":block.nonce,
                    "block_hash":block.block_hash,
                    "transactions":transactions}
            bts = block.block_timestamp
            if isinstance(bts,datetime):
                b["block_timestamp"]=bts.timestamp()
            chain.append(b)
        
        return chain


    def create_genesis(self):
        dt = datetime.fromtimestamp(0)
        genesis = Block(0,"0",dt)
        db.session.add(genesis)
        db.session.commit()
        proof=self.proof_work(0)
        self.add_block(0,proof)

    def new_transaction(self,transaction):
        self.unconfirmed_transactions.append(transaction)

    def mine(self):
        if not self.unconfirmed_transactions:
            return False
        
        last_block = self.last_block
        new_block = Block(last_block["id"]+1,last_block["block_hash"])
        #===========================================
        db.session.add(new_block)
        db.session.commit()

        new_block=Block.query.get(last_block["id"]+1)
        new_block.add_tx(self.unconfirmed_transactions)
        db.session.commit()
        #=========================================
        
        new_id = last_block["id"]+1
        proof=self.proof_work(new_id)
        
        self.add_block(new_id,proof)
        self.unconfirmed_transactions=[]
        return new_block.id




    @property
    def last_block(self):
        return self.chain[-1]

    @staticmethod
    def proof_work(block_id):
        
        block = Block.query.get(block_id)
        block.nonce = 0
        computed_hash = block.compute_hash()
        while not computed_hash.startswith('0'*Blockchain.difficulty):
            block.nonce+=1
            computed_hash=block.compute_hash()
        db.session.commit()
        return computed_hash

    def add_block(self, block_id, proof):
        
        block = Block.query.get(block_id)
        
        if block_id==0:
            previous_hash="0"
        else:    
            previous_hash = self.last_block["block_hash"]

        if previous_hash != block.previous_hash:
            #print("hash did not match")
            #print(previous_hash)
            #print(block.previous_hash)
            Transaction.query.filter_by(block_id=block.id).delete()
            Block.query.filter_by(id=block.id).delete() 
            db.session.commit()
            return False

        if not Blockchain.is_valid_proof(block_id, proof):
            #print("is valid proof failed")
            Transaction.query.filter_by(block_id=block.id).delete()
            Block.query.filter_by(id=block.id).delete()
            db.session.commit()
            return False

        block.set_hash(proof)
        db.session.commit()
        self.chain=self.return_chain()
        return True

    @classmethod
    def is_valid_proof(self, block_id, block_hash):
        
        block = Block.query.get(block_id)
        return (block_hash.startswith('0' * Blockchain.difficulty) and
                block_hash == block.compute_hash())

    @classmethod
    def is_valid(self,block,block_hash):
        #print(block)
        x= (block_hash.startswith('0'*Blockchain.difficulty) and
                block_hash == self.check_hash(block))
        print("inside is valid {}".format(x))
        return x


    @classmethod
    def check_chain_validity(self,chain):
        result = True
        previous_hash= "0"

        for block in chain:
            block_hash = block["block_hash"]
            del block["block_hash"] 
            if not self.is_valid(block,block_hash) or \
                    previous_hash != block["previous_hash"]:
                        result=False
                        break
            block["block_hash"],previous_hash = block_hash,block_hash
        #print("check chain vaildity result is {}".format(result))
        return result
    
    @staticmethod
    def create_instance(block):
        new_block=dict() 
        keys = list(block.keys())
        for key in keys:
            if key in ["id","transactions","block_timestamp","previous_hash","nonce"]:
                new_block[key]=block[key]

        return new_block

    @staticmethod
    def check_hash(block):
        
        block_str=json.dumps(block,sort_keys=True)
        return sha256(block_str.encode()).hexdigest()

