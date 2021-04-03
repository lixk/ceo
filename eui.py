import base64
import hashlib
import json
import os
import random
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

_RECEIVE_QUEUE = Queue()
_SEND_QUEUE = Queue()
_DISPATCHERS = ThreadPoolExecutor(max_workers=100)
handlers = {}

_JS_TEMPLATE = '''
var ws = new WebSocket("ws://localhost:%s");
ws.onopen = function () {
 console.log('connect to server!');
}

ws.onmessage = function (evt) {
 var data = JSON.parse(evt.data);
 data = data['handler']+'.apply(null, '+JSON.stringify(data['args'])+')';
 eval(data);
}

ws.onclose = function () {
 alert("发生异常，请重新运行软件！");
}

window.eui = {}
window.eui.py = function(handler){
 var args = [];
 for(var i=1; i<arguments.length; i++){
    args.push(arguments[i]);
 }
 ws.send(JSON.stringify({'handler': handler, 'args': args}));
}
'''


def _get_headers(data):
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

    bytes_list = bytearray()

    for i in range(len(decoded)):
        chunk = decoded[i] ^ mask[i % 4]
        bytes_list.append(chunk)
    body = str(bytes_list, encoding='utf-8')
    return body


def _send_msg(conn, msg_bytes):
    token = b"\x81"
    length = len(msg_bytes)
    if length < 126:
        token += struct.pack("B", length)
    elif length <= 0xFFFF:
        token += struct.pack("!BH", 126, length)
    else:
        token += struct.pack("!BQ", 127, length)

    msg = token + msg_bytes
    conn.sendall(msg)
    return True


def start(host="0.0.0.0", port=None, static_dir='./static', startup_callback=None,
          max_message_size=1 * 1024 * 1024):
    if port is None:
        port = random.randint(5000, 10000)

    _init_js(port, static_dir)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)

    _startup_callback(startup_callback)
    print('-' * 10, f' eui server start up at port {port} ', '-' * 10)

    conn, addr = sock.accept()
    print(conn)
    data = conn.recv(max_message_size)
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
    conn.sendall(bytes(response_str, encoding="utf-8"))
    # startup dispatcher and send message worker
    _startup_dispatcher()
    _startup_send_message_worker(conn)

    while True:
        data = conn.recv(max_message_size)
        _RECEIVE_QUEUE.put(json.loads(_parse_payload(data)))


def _init_js(port, static_dir):
    os.makedirs(static_dir, exist_ok=True)
    with open(f'{static_dir}/eui.js', 'w', encoding='utf-8') as f:
        f.write(_JS_TEMPLATE % port)


def _startup_dispatcher():
    def run():
        while True:
            data = _RECEIVE_QUEUE.get()
            handler = handlers[data['handler']]
            args = data.get('args', None)
            if args:
                _DISPATCHERS.submit(handler, *args)
            else:
                _DISPATCHERS.submit(handler)

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def _startup_send_message_worker(conn):
    def run():
        while True:
            data = _SEND_QUEUE.get()
            _send_msg(conn, data.encode('utf-8'))

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def _startup_callback(fn):
    if not fn:
        return
    callback_thread = threading.Thread(target=fn)
    callback_thread.setDaemon(True)
    callback_thread.start()


def js(handler, *args):
    data = json.dumps({'handler': handler, 'args': args}, ensure_ascii=True)
    _SEND_QUEUE.put(data)


def hello(name):
    js('hello', name)


if __name__ == "__main__":
    handlers['hello'] = hello
    start()
