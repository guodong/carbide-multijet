from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


class S(BaseHTTPRequestHandler):

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])  # <--- Gets the size of data
        post_data = self.rfile.read(content_length)  # <--- Gets the data itself
        print post_data
        self.send_response(200)


class FlowServer(Thread):
    def __init__(self, port=7777):
        super(FlowServer, self).__init__()
        self.port = port

    def run(self):
        server_address = ('', self.port)
        httpd = HTTPServer(server_address, S)
        print 'Starting FlowServer...'
        httpd.serve_forever()
