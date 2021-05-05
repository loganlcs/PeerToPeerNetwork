import socket, random
import threading
import pickle
import sys
import time
import hashlib
import os
from collections import OrderedDict


# DEFAULT-VALUES
IP = "127.0.0.1"
PORT = 1
buffer = 4096
MAX_BITS = 10        
MAX_NODES = 2 ** MAX_BITS

# Takes key string, uses SHA-1 hashing and returns a 10-bit (1024) compressed integer
def getHash(key):
    result = hashlib.sha1(key.encode())
    return int(result.hexdigest(), 16) % MAX_NODES
 
class Node:
    #Assign values to data members
    def __init__(self, ip, port):
        self.filenameList = []            #List of files this node has
        self.ip = ip                      #IP of Node
        self.port = port                  #Port of Node
        self.address = (ip, port)         #Address of Node
        self.id = getHash(ip + ":" + str(port)) #Node ID is hashed from ip and port
        self.pred = (ip, port)            # Predecessor of Node
        self.predID = self.id             # Predecessor ID
        self.succ = (ip, port)            # Successor to Node
        self.succID = self.id             # Successor ID
        self.fingerTable = OrderedDict()  # Dictionary: key = IDs and value = (IP, port) tuple

        # SOCKETS
        # The server socket will listen for any joining nodes
        try:
            self.ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.ServerSocket.bind((IP, PORT))
            self.ServerSocket.listen()
        except socket.error:
            print("Socket did not open, Restart Node")

    #Thread listens for connection on server sockets then creates a connection thread
    def listenThread(self):
        # Stores IP and port in address and saves connection and threading
        while True:
            try:
                connection, address = self.ServerSocket.accept()
                connection.settimeout(120)
                threading.Thread(target=self.connectionThread, args=(connection, address)).start()
            except socket.error:
                pass

    # Thread for each connection
    def connectionThread(self, connection, address):
        #Use pickle to load the recieved data list when a node is connected
        rDataList = pickle.loads(connection.recv(buffer))
        #CONNECTIONS
        #Depending on the first int of the recieved data list the type of connection is executed 
        # Types: 0: peer connect 1: client 2: ping 3: lookupID 4: updateSucc/Pred
        connectionType = rDataList[0]
        if connectionType == 0:
            print("Connection with:", address[0], ":", address[1])
            print("Join network request received")
            self.joinNode(connection, address, rDataList)
            self.Menu()
        elif connectionType == 1:
            print("Connection with:", address[0], ":", address[1])
            print("Upload/Download request received")
            self.transferFile(connection, address, rDataList)
            self.Menu()
        elif connectionType == 2:
            #print("Ping recevied")
            connection.sendall(pickle.dumps(self.pred))
        elif connectionType == 3:
            #print("Lookup request recevied")
            self.lookupID(connection, address, rDataList)
        elif connectionType == 4:
            #print("Predecessor/Successor update request recevied")
            if rDataList[1] == 1:
                self.updateSucc(rDataList)
            else:
                self.updatePred(rDataList)
        elif connectionType == 5:
            # print("Update Finger Table request recevied")
            self.updateFTable()
            connection.sendall(pickle.dumps(self.succ))
        else:
            print("Problem getting connection type")
    
    # Deals with join network request by other node
    def joinNode(self, connection, address, rDataList):
        if rDataList:
            peerIPport = rDataList[1]
            peerID = getHash(peerIPport[0] + ":" + str(peerIPport[1]))
            oldPred = self.pred
            # Update prede
            self.pred = peerIPport
            self.predID = peerID
            # Sends new peer's pred back 
            sDataList = [oldPred]
            connection.sendall(pickle.dumps(sDataList))
            #Update F table
            time.sleep(0.1)
            self.updateFTable()
            # Update other peers F tables
            self.updateOtherFTables()

    def transferFile(self, connection, address, rDataList):
        # Choice: 0 for download, 1 for upload
        choice = rDataList[1]
        filename = rDataList[2]
        fileID = getHash(filename)
        # If client wants to download file
        if choice == 0:
            print("Download request file:", filename)
            try:
                # Searches its directory to see if file exists
                if filename not in self.filenameList:
                    connection.send("NotFound".encode('utf-8'))
                    print("File not found")
                 # If file exists in the directory it sends the file
                else:  
                    connection.send("Found".encode('utf-8'))
                    self.sendFile(connection, filename)
            except ConnectionResetError as error:
                print(error, "\nClient disconnected\n\n")
        # If client wants to upload file
        elif choice == 1 or choice == -1:
            print("Receiving file:", filename)
            fileID = getHash(filename)
            #print("Uploading file ID:", fileID)
            self.filenameList.append(filename)
            self.receiveFile(connection, filename)
            print("Upload complete")
            # Replicating file to successor 
            if choice == 1:
                if self.address != self.succ:
                    self.uploadFile(filename, self.succ, False)

#Looks up the ID and determines which address to send 
    def lookupID(self, connection, address, rDataList):
        keyID = rDataList[1]
        sDataList = []
        # print(self.id, keyID)
        if self.id == keyID:        # Case 0: If keyId at self
            sDataList = [0, self.address]
        elif self.succID == self.id:  # Case 1: If only one node
            sDataList = [0, self.address]
        elif self.id > keyID:       # Case 2: Node id greater than keyId, ask pred
            if self.predID < keyID:   # If pred is higher than key, then self is the node
                sDataList = [0, self.address]
            elif self.predID > self.id:
                sDataList = [0, self.address]
            else:       # Else send the pred back
                sDataList = [1, self.pred]
        else:           # Case 3: node id less than keyId USE fingertable to search
            # IF last node before chord circle completes
            if self.id > self.succID:
                sDataList = [0, self.succ]
            else:
                value = ()
                for key, value in self.fingerTable.items():
                    if key >= keyID:
                        break
                value = self.succ
                sDataList = [1, value]
        connection.sendall(pickle.dumps(sDataList))

#Updates successor of this node
    def updateSucc(self, rDataList):
        newSucc = rDataList[2]
        self.succ = newSucc
        self.succID = getHash(newSucc[0] + ":" + str(newSucc[1]))

#Updates predecessor of this node
    def updatePred(self, rDataList):
        newPred = rDataList[2]
        self.pred = newPred
        self.predID = getHash(newPred[0] + ":" + str(newPred[1]))

    def start(self):
        # Starts accepting connections from other threads
        threading.Thread(target=self.listenThread, args=()).start()
        threading.Thread(target=self.pingSucc, args=()).start()
        # In case of connecting to other clients
        while True:
            print("Listening for other clients...")   
            self.asAClientThread()

  #Pings successor   
    def pingSucc(self):
        while True:
            # Ping every 5 seconds
            time.sleep(2)
            # If one node only, no pinging necessary
            if self.address == self.succ:
                continue
            try:
                pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                pSocket.connect(self.succ)
                pSocket.sendall(pickle.dumps([2]))  # Send ping request for connection thread
                recvPred = pickle.loads(pSocket.recv(buffer))
            except:
                print("\nNode has gone offline. Reconfiguring network...")
                # If a node leaves, updates succ
                newSuccFound = False
                value = ()
                for key, value in self.fingerTable.items():
                    if value[0] != self.succID:
                        newSuccFound = True
                        break
                if newSuccFound:
                    self.succ = value[1]   # Update Node succ to new succ
                    self.succID = getHash(self.succ[0] + ":" + str(self.succ[1]))
                    # Tell new succ to make this node pred
                    pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    pSocket.connect(self.succ)
                    pSocket.sendall(pickle.dumps([4, 0, self.address])) #Send update pred/succ request
                    pSocket.close()
                else:       # If only node left
                    self.pred = self.address            # Make self pred
                    self.predID = self.id
                    self.succ = self.address            # Make self succ
                    self.succID = self.id
                self.updateFTable()
                self.updateOtherFTables()
                self.Menu()

    # Handler for user input for options
    def asAClientThread(self):
        self.Menu()
        userChoice = input()
        if userChoice == "1":
            ip = input("Enter IP: ")
            port = input("Enter port: ")
            self.sendJoinRequest(ip, int(port))
        elif userChoice == "2":
            self.leaveNetwork()
        elif userChoice == "3":
            filename = input("Enter filename: ")
            fileID = getHash(filename)
            recvIPport = self.getSuccessor(self.succ, fileID)
            self.uploadFile(filename, recvIPport, True)
        elif userChoice == "4":
            filename = input("Enter filename: ")
            self.downloadFile(filename)
        elif userChoice == "5":
            print("My ID:", self.id, "Predecessor:", self.predID, "Successor:", self.succID)

    #Send join request to inputted ip and port 
    def sendJoinRequest(self, ip, port):
        try:
            recvIPPort = self.getSuccessor((ip, port), self.id)
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peerSocket.connect(recvIPPort)
            sDataList = [0, self.address]
            peerSocket.sendall(pickle.dumps(sDataList))     # Sending self peer address to be added to network
            rDataList = pickle.loads(peerSocket.recv(buffer))   # Receiving new pred
            # Updating pred and succ
            self.pred = rDataList[0]
            self.predID = getHash(self.pred[0] + ":" + str(self.pred[1]))
            self.succ = recvIPPort
            self.succID = getHash(recvIPPort[0] + ":" + str(recvIPPort[1]))
            # Tell pred to update its successor which is this node using update pred/succ connection thread
            sDataList = [4, 1, self.address]
            pSocket2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pSocket2.connect(self.pred)
            pSocket2.sendall(pickle.dumps(sDataList))
            pSocket2.close()
            peerSocket.close()
            print("Connection successful! Connected to #ID: " + str(self.predID))
        except socket.error:
            print("Socket error. Incorrect IP/Port")
    
    #Leave network this node is connected to
    def leaveNetwork(self):
        # Tell succ to update pred
        pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pSocket.connect(self.succ)
        pSocket.sendall(pickle.dumps([4, 0, self.pred]))
        pSocket.close()
        # Tell pred to update succ
        pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        pSocket.connect(self.pred)
        pSocket.sendall(pickle.dumps([4, 1, self.succ]))
        pSocket.close()
        print("Files:", self.filenameList)
        # Copying files to succ
        print("Copying files...")
        for filename in self.filenameList:
            pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            pSocket.connect(self.succ)
            sDataList = [1, 1, filename]
            pSocket.sendall(pickle.dumps(sDataList))
            with open(filename, 'rb') as file:
                pSocket.recv(buffer)
                self.sendFile(pSocket, filename)
                pSocket.close()
                print("File has been copied")
            pSocket.close()
        
        self.updateOtherFTables()   # Update f tables
        
        self.pred = (self.ip, self.port)    # Set succ and pred to self
        self.predID = self.id
        self.succ = (self.ip, self.port)
        self.succID = self.id
        self.fingerTable.clear()
        print(self.address, "has left the network")
    
    # Upload File selected
    def uploadFile(self, filename, recvIPport, replicate):
        print("Uploading file", filename)
        # If not found send lookup request to get peer to upload file
        sDataList = [1]
        if replicate:
            sDataList.append(1)
        else:
            sDataList.append(-1)
        try:
            # Check if file is in directory
            file = open(filename, 'rb')
            file.close()
            sDataList = sDataList + [filename]
            cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cSocket.connect(recvIPport)
            cSocket.sendall(pickle.dumps(sDataList))
            #Send file data
            self.sendFile(cSocket, filename)
            cSocket.close()
            print("Success! File has been uploaded")
        except IOError:
            print("File not in directory")
        except socket.error:
            print("Error when uploading file")
    
    #Download File input
    def downloadFile(self, filename):
        print("Downloading file", filename)
        fileID = getHash(filename)
        # First finding node with the file
        recvIPport = self.getSuccessor(self.succ, fileID)
        sDataList = [1, 0, filename]
        cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cSocket.connect(recvIPport)
        cSocket.sendall(pickle.dumps(sDataList))      
        # Receiving confirmation if file found or not
        fileData = cSocket.recv(buffer)
        if fileData == b"NotFound":
            print("File not found:", filename)
        else:
            print("Receiving file:", filename)
            self.receiveFile(cSocket, filename)


    #Function to find successor of node
    def getSuccessor(self, address, keyID):
        rDataList = [1, address]     
        recvIPPort = rDataList[1]
        while rDataList[0] == 1:
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                peerSocket.connect(recvIPPort)
                # Send continous ping request
                sDataList = [3, keyID]
                peerSocket.sendall(pickle.dumps(sDataList))
                # Do continous lookup until you get your postion (0)
                rDataList = pickle.loads(peerSocket.recv(buffer))
                recvIPPort = rDataList[1]
                peerSocket.close()
            except socket.error:
                print("Could not connect when finding successor")
        # returns reciever IP port
        return recvIPPort
    
    def updateFTable(self):
        for i in range(MAX_BITS):
            entryId = (self.id + (2 ** i)) % MAX_NODES
            # If only one node in network
            if self.succ == self.address:
                self.fingerTable[entryId] = (self.id, self.address)
                continue
            # If multiple nodes in network find succ for each entryID
            recvIPPort = self.getSuccessor(self.succ, entryId)
            recvId = getHash(recvIPPort[0] + ":" + str(recvIPPort[1]))
            self.fingerTable[entryId] = (recvId, recvIPPort)
    
    def updateOtherFTables(self):
        here = self.succ
        while True:
            if here == self.address:
                break
            pSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                pSocket.connect(here)  # Connecting to server
                pSocket.sendall(pickle.dumps([5]))
                here = pickle.loads(pSocket.recv(buffer))
                pSocket.close()
                if here == self.succ:
                    break
            except socket.error:
                print("Connection denied")

    #Sends file data
    def sendFile(self, connection, filename):
        print("Sending file:", filename)
        try:
            # Reading file data size
            with open(filename, 'rb') as file:
                data = file.read()
                print("File size:", len(data))
                fileSize = len(data)
        except:
            print("File not found")
        try:
            with open(filename, 'rb') as file:
                while True:
                    fileData = file.read(buffer)
                    time.sleep(0.001)
                    if not fileData:
                        break
                    connection.sendall(fileData)
        except:
            pass
        print("File sent")

    def receiveFile(self, connection, filename):
        # Check if file is already in directory
        fileAlready = False
        try:
            with open(filename, 'rb') as file:
                data = file.read()
                size = len(data)
                if size == 0:
                    print("File size 0, resending request")
                    fileAlready = False
                else:
                    print("File already present")
                    fileAlready = True
                return
        except FileNotFoundError:
            pass
        if not fileAlready:
            totalData = b''
            recvSize = 0
            try:
                with open(filename, 'wb') as file:
                    while True:
                        fileData = connection.recv(buffer)
                        recvSize += len(fileData)
                        if not fileData:
                            break
                        totalData += fileData
                    file.write(totalData)
            except ConnectionResetError:
                print("Data transfer interupted")
                time.sleep(5)
                os.remove(filename)
                time.sleep(5)
                self.downloadFile(filename)

    def Menu(self):
        print("\nID#:", myNode.id)
        print("\n1. Join Network\n2. Leave Network\n3. Upload File\n4. Download File")
        print("5. Print my predecessor and successor")

if len(sys.argv) < 3:
    print("Default IP and Port selected\nIP: 127.0.0.1\nPORT: 1")
else:
    IP = sys.argv[1]
    PORT = int(sys.argv[2])

myNode = Node(IP, PORT)
print("ID#:", myNode.id)
myNode.start()
myNode.ServerSocket.close()
