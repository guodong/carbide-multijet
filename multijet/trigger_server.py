from threading import Thread
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from urlparse import urlparse, parse_qs

on_trigger_handler = None


class S(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        type = 'get_rules'
        if query_components.has_key('type'):
            type = query_components["type"][0]

        self._set_headers()
        self.wfile.write("triggered")
        on_trigger_handler(type, query_components)


class TriggerServer(Thread):
    def __init__(self, on_trigger):
        super(TriggerServer, self).__init__()
        global on_trigger_handler
        on_trigger_handler = on_trigger

    def run(self):
        server_address = ('', 6666)
        httpd = HTTPServer(server_address, S)
        print 'Starting TriggerServer...'
        httpd.serve_forever()
