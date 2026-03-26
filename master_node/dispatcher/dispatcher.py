from http.server import HTTPServer

from master_node.dispatcher.app import RequestHandler



def run_dispatcher(port: int):
    server = HTTPServer(('', port), RequestHandler)
    print(f"dispatcher запущен на http://localhost:{port}")
    server.serve_forever()
