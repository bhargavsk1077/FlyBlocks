# FlyBlocks

A Python Blockchain implementation using Flask 

## Installation

1. Clone the repository
2. Install the requirements using `pip install -r requirements.txt`
3. Export your database Url if any , or a sqlite database will be used by defualt
4. set your flask app environment variable with `export FLASK_APP=block_server.py`
5. initialise your database by following the commands in order:

   * `flask db init`
   * `flask db migrate`
   * `flask db upgrade`
 6. start the server on the required port with `flask run --port 8000`
 7. run the client app with `python run_app.py`

## Usage

### Client

* wirte something you want to post and fill in your username and click on **post**
* add as many posts as you want and click on **request to mine**, which will mine a new block with the unconfirmed transactions(posts)
* click on **resync** to get your newly added posts 

### Connecting to new Nodes

* you can connct to new nodes by sending post requests using curl or postman (your preferance). 

   like so :
   ```
   $ curl -X POST \
  http://<address-of-node-sending-connection-request>/register_with \
  -H 'Content-Type: application/json' \
  -d '{"node_address": "<address-of-node-you-wish-to-connect-with>"}
   ```
* When the connection is succesusful, the whole blockchain created again so that all the connected nodes have the same chain
* minig a block in one of the nodes will add the respective block to all other nodes
* **Note** : Different nodes will need to have different Database Urls

## Source and Changes
### Source
You can find the tutorial to build a pyhton blockchain [here](https://developer.ibm.com/technologies/blockchain/tutorials/develop-a-blockchain-application-from-scratch-in-python/)
and link to the github repo [here](https://github.com/satwikkansal/python_blockchain_app)

### Changes
The implementation of blockchain in the mentianed sources is done in a way where the whole blockchain instance is stored in memory. You can take a look at that code in **blockchain.py**

So shutting down the server will cause loss of all the blocks and transactions.

In my Implementation of the same, I have given the server a database support so that all the blocks and transactions are stored in the database instead of memory. So the servers can be closed without losing data as the chain is re-initialised from the database when started again.

No changes have been made to the Client app.





