import base64
import hashlib
import json
import logging
import os
import queue
import random
import socket
import struct
import threading
from concurrent import futures

log = logging.getLogger('eui')
_RECEIVE_QUEUE = queue.Queue()
_SEND_QUEUE = queue.Queue()
_DISPATCHERS = futures.ThreadPoolExecutor(max_workers=100)
_HANDLERS = {}

# eui.js template
_JS_TEMPLATE = '''//eui client
var ws = new WebSocket("ws://localhost:%s");
ws.onopen = function () {
   console.log('connect to eui server!');
}

ws.onmessage = function (evt) {
   var data = JSON.parse(evt.data);
   data = data['handler'] + '.apply(null, ' + JSON.stringify(data['args']) + ')';
   eval(data);
}

ws.onclose = function () {
   alert('APP will exit!');
   window.location.href = "about:blank";
   window.close();
}

window.eui = {}
window.eui.py = function (handler, args___) {
   var args = [];
   for (var i = 1; i < arguments.length; i++) {
      args.push(arguments[i]);
   }
   ws.send(JSON.stringify({ 'handler': handler, 'args': args }));
}

'''


def _init_log(file, level):
    """
    init log config
    :param file: log file
    :param level: log level
    :return:
    """

    log.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(pathname)s [line:%(lineno)d] %(message)s",
                                  '%Y-%m-%d %H:%M:%S')
    console_log_handler = logging.StreamHandler()
    console_log_handler.setFormatter(formatter)
    file_log_handler = logging.FileHandler(file, mode='w')
    file_log_handler.setFormatter(formatter)

    log.addHandler(console_log_handler)
    log.addHandler(file_log_handler)


def _get_headers(data):
    """
    get headers from data
    :param data: parsed message
    :return: headers
    """
    headers = {}
    data = str(data, encoding="utf-8")
    header_str, body = data.split("\r\n\r\n", 1)
    header_list = header_str.split("\r\n")
    headers['method'], headers['protocol'] = header_list[0].split(' ', 1)
    for row in header_list[1:]:
        key, value = row.split(":", 1)
        headers[key] = value.strip()

    return headers


def _parse_payload(payload):
    """
    parse payload message

    :param payload: message
    :return: parsed string message
    """

    payload_len = payload[1] & 127
    if payload_len == 126:
        mask = payload[4:8]
        decoded = payload[8:]

    elif payload_len == 127:
        mask = payload[10:14]
        decoded = payload[14:]
    else:
        mask = payload[2:6]
        decoded = payload[6:]

    byte_list = bytearray()
    for i, b in enumerate(decoded):
        chunk = b ^ mask[i % 4]
        byte_list.append(chunk)

    if byte_list == bytearray(b'\x03\xe9'):
        log.info('client closed, eui exit!')
        os._exit(0)
    return str(byte_list, encoding='utf-8')


def _send_msg(connection, message_bytes):
    """
    send message to client

    :param connection: connection
    :param message_bytes: message bytes
    :return:
    """
    token = b"\x81"
    length = len(message_bytes)
    if length < 126:
        token += struct.pack("B", length)
    elif length <= 0xFFFF:
        token += struct.pack("!BH", 126, length)
    else:
        token += struct.pack("!BQ", 127, length)

    msg = token + message_bytes
    connection.sendall(msg)


def _init_js(port, static_dir):
    """
    generate js file

    :param port: eui server port
    :param static_dir: dir for eui.js
    :return:
    """
    os.makedirs(static_dir, exist_ok=True)
    with open(f'{static_dir}/eui.js', 'w', encoding='utf-8') as f:
        f.write(_JS_TEMPLATE % port)


def _startup_dispatcher():
    def run():
        while True:
            data = _RECEIVE_QUEUE.get()
            handler_name = data.get('handler', '')
            if handler_name not in _HANDLERS:
                log.error(f"handler '{handler_name}' not found, please check handlers config")
                os.abort()
            handler = _HANDLERS[handler_name]
            args = data.get('args', None)
            if args:
                _DISPATCHERS.submit(handler, *args)
            else:
                _DISPATCHERS.submit(handler)

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def _startup_send_message_worker(connection):
    def run():
        while True:
            data = _SEND_QUEUE.get()
            _send_msg(connection, data.encode('utf-8'))

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def _startup_callback(fn):
    """
    startup callback function
    :param fn: callback function
    :return:
    """
    if not fn:
        return
    callback_thread = threading.Thread(target=fn)
    callback_thread.setDaemon(True)
    callback_thread.start()


def js(handler, *args):
    """
    call js function

    :param handler: js function
    :param args: js function args
    :return:
    """
    data = json.dumps({'handler': handler, 'args': args}, ensure_ascii=True)
    _SEND_QUEUE.put(data)


def start(host="0.0.0.0", port=None, handlers=None, static_dir='./static', startup_callback=None,
          max_message_size=1 * 1024 * 1024, log_file='eui.log', log_level='DEBUG'):
    """
    start eui

    :param host: host
    :param port: port, if port is None, port will be a random int value
    :param handlers: python function for js call
    :param static_dir: generate js file path, could not end with '/'
    :param startup_callback: the function after eui startup to run
    :param max_message_size: each message max size
    :param log_file: log file
    :param log_level: log level, 'CRITICAL', 'FATAL', 'ERROR', 'WARN', 'WARNING', 'INFO', 'DEBUG', 'NOTSET'
    :return:
    """

    global _HANDLERS

    # init log
    _init_log(log_file, log_level)

    # init port
    if port is None:
        port = random.randint(5000, 50000)

    # init handlers
    if handlers:
        _HANDLERS = handlers

    # init js file
    _init_js(port, static_dir)

    # init socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(0)

    # startup callback function
    _startup_callback(startup_callback)
    log.info(f'\n******************** eui start up at port {port} ********************')

    # accept connection
    connection, addr = sock.accept()
    log.info(f'client {addr} connect success!')

    # receive connection message
    data = connection.recv(max_message_size)
    headers = _get_headers(data)
    response_tpl = "HTTP/1.1 101 Switching Protocols\r\n" \
                   "Upgrade:websocket\r\n" \
                   "Connection: Upgrade\r\n" \
                   "Sec-WebSocket-Accept: %s\r\n" \
                   "WebSocket-Location: ws://%s\r\n\r\n"

    magic_string = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    value = ''
    if headers.get('Sec-WebSocket-Key'):
        value = headers['Sec-WebSocket-Key'] + magic_string
    ac = base64.b64encode(hashlib.sha1(value.encode('utf-8')).digest())
    response_str = response_tpl % (ac.decode('utf-8'), headers.get("Host"))
    connection.sendall(bytes(response_str, encoding="utf-8"))

    # startup dispatcher and send message worker
    _startup_dispatcher()
    _startup_send_message_worker(connection)

    # receive client message
    while True:
        data = connection.recv(max_message_size)
        _RECEIVE_QUEUE.put(json.loads(_parse_payload(data)))


def hello(name):
    js('hello', name)


if __name__ == "__main__":
    _HANDLERS['hello'] = hello
    start()
