import socketserver
import struct

class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    def handle(self):
        # self.request is the TCP socket connected to the client
        self.data = self.request.recv(1024).strip()
        print("{} wrote:".format(self.client_address[0]))
        print(self.data)
        # just send back the same data
        self.request.sendall(self.data)

class MyHWLHandler(socketserver.BaseRequestHandler):
    def handle(self):
        # self.request is the TCP socket connected to the client
        dataBytes = self.request.recv(1024)

        print("{} wrote:".format(self.client_address[0]))
        print(dataBytes)
        # just send back the same data
        self.request.sendall(dataBytes)

if __name__ == "__main__":
    HOST, PORT = "localhost", 6000

    # Create the server, binding to localhost on port 9999
    with socketserver.TCPServer((HOST, PORT), MyHWLHandler) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C
        server.daemon_threads = True
        server.allow_reuse_address = True
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            sys.exit(0)
