Logan Gresko
Lab Peer-to-Peer Network

Node Connection Walkthrough:
This project follows the Chord topology for a peer-to-peer distributed hash table. Each Node has a 
predecessor and successor that update as peers join and leave the network. When a Node is started it 
begins accepting connections from other Nodes with a listening thread which creates the server socket,
 binds it to the current node’s IP and port and listens for clients.Another instance of Node is 
started and selects the Join Network option which prompts the user for an IP and a port. Once 
inputted, the program finds the successor IP port using the given IP and port number and creates a 
peer socket to connect to the successor. Once connected it sends the server node it’s address to be 
added to the network and updates its predecessors and successors. This also tells the predecessor to 
update its successor to the current Node. 

Everytime a connection is made between Nodes a connection type value is passed along with the address
of the Node sending the connection in a connection thread. The connection type determines how both 
nodes will interact with another, the options being: join node to the network, transfer file request,
ping, lookup ID request, update successor/predecessor, and update finger table. To upload a file to 
the network, a Node selects the Upload File option and enters a filename. If the file is found it is 
uploaded to the network and received by all Nodes in the network. If for whatever reason a Node does 
not receive the file, selecting the Download File option and entering the filename will download the 
file from the owner Node. Each node has a finger table which keeps track of the keyIDs in the network.
This is used in the lookup ID connection thread to search for the address that needs to be sent. 
If a Node goes offline, the ping being sent to the offline node notifies that it has gone offline and
updates its successors and neighboring Nodes successors/predecessors. If a client leaves the network,
it tells its successor and predecessor to update then copies any files in its directory to the other
Nodes in the network. Once done it sets itself to its own pred/succ and closes the peer socket.

Overall this project taught me alot about distributed networks and the design of chord topology. It 
made me get experience in making networks in python and dealing with socket connections and threads. 
Though it was difficult to understand how to implement at first it became more understandable with 
time.
