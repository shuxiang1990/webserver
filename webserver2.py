# coding: utf-8
import socket
import sys
import StringIO
import errno
import os
import signal


class WSGIServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1024

    def __init__(self, server_address):

        self.listen_socket = listen_socket = socket.socket(
            self.address_family,
            self.socket_type
        )
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        # get hostname and port
        host, port = listen_socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.headers_set = []


    def grim_reaper(self, signum, frame):

        while True:
            try:
                pid, status = os.waitpid(
                    -1,  # Wait for any child process
                    os.WNOHANG  # Do not block and return EWOULDBLOCK error
                )
            except OSError:
                return

            if pid == 0:  # no more zombies
                return

    def serve_forever(self):

        signal.signal(signal.SIGCHLD, self.grim_reaper)
        listen_socket = self.listen_socket
        while True:

            try:
                client_connection, client_address = listen_socket.accept()
            except IOError, e:
                code, msg = e.args
                if code == errno.EINTR:
                    continue
                else:
                    raise
            pid = os.fork()
            if pid == 0:
                listen_socket.close()
                self.handle_request(client_connection)
                client_connection.close()
                os._exit(0)
            else:
                client_connection.close()


    def handle_request(self, client_connection):
        self.request_data = request_data = client_connection.recv(1024)
        print (''.join('< {line}\n'.format(line=line) for line in request_data.splitlines()))

        # 解析请求的第一行
        self.parse_request(request_data)

        # 获取请求过来的环境变量
        env = self.get_environ()

        # 调用应用程序框架，返回请求结果内容
        result = self.application(env, self.start_response)

        # 构造好返回包并响应请求
        self.finish_response(result, client_connection)

    def set_app(self, app):
        self.application = app

    def parse_request(self, text):
        # 解析请求的第一行信息
        request_line = text.splitlines()[0].rstrip('\r\n')
        (self.request_method,  # GET
         self.path,  # /hello
         self.request_version  # http/1.1
         ) = request_line.split()

    def get_environ(self):
        env = {}

        # Required WSGI variables
        env['wsgi.version'] = (1, 0)
        env['wsgi.url_scheme'] = 'http'
        env['wsgi.input'] = StringIO.StringIO(self.request_data)
        env['wsgi.errors'] = sys.stderr
        env['wsgi.multithread'] = False
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once'] = False
        # Required CGI variables
        env['REQUEST_METHOD'] = self.request_method  # GET
        env['PATH_INFO'] = self.path  # /hello
        env['SERVER_NAME'] = self.server_name  # localhost
        env['SERVER_PORT'] = str(self.server_port)  # 8888
        return env

    def start_response(self, status, response_headers, exc_info=None):
        # 这里添加必要的头部信息
        server_headers = [
            ('Date', 'Tue, 31 Mar 2015 12:54:48 GMT'),
            ('Server', 'WSGIServer 0.2')
        ]
        self.headers_set = [status, response_headers + server_headers]
        # 根据 wsgi 规范， start_response 必须返回一个 ‘write’ callable，
        # 这里简化处理了

    def finish_response(self, result, client_connection):

        try:
            status, response_headers = self.headers_set
            response = 'HTTP/1.1 {status}\r\n'.format(status=status)
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'

            for data in result:
                response += data

            print(''.join(
                '> {line}\n'.format(line=line)
                for line in response.splitlines()
            ))
            client_connection.sendall(response)

        finally:
            client_connection.close()


SERVER_ADDRESS = (HOST, PORT) = '', 8888


def make_server(server_address, application):
    server = WSGIServer(server_address)
    server.set_app(application)
    return server


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Provide a WSGI application object as module:callable')
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = __import__(module)
    application = getattr(module, application)
    httpd = make_server(SERVER_ADDRESS, application)
    print('WSGIServer: Serving HTTP on port {port} ...\n'.format(port=PORT))
    httpd.serve_forever()