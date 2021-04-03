import base64
import hashlib
import json
import socket
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

receive_queue = Queue()
send_queue = Queue()
handlers = {}
dispatchers = ThreadPoolExecutor(max_workers=100)


def get_headers(data):
    headers = {}
    data = str(data, encoding="utf-8")
    header_str, body = data.split("\r\n\r\n", 1)
    header_list = header_str.split("\r\n")
    headers['method'], headers['protocol'] = header_list[0].split(' ', 1)
    for row in header_list[1:]:
        key, value = row.split(":", 1)
        headers[key] = value.strip()

    return headers


def parse_payload(payload):
    payload_len = payload[1] & 127
    if payload_len == 126:
        extend_payload_len = payload[2:4]
        mask = payload[4:8]
        decoded = payload[8:]

    elif payload_len == 127:
        extend_payload_len = payload[2:10]
        mask = payload[10:14]
        decoded = payload[14:]
    else:
        extend_payload_len = None
        mask = payload[2:6]
        decoded = payload[6:]

    bytes_list = bytearray()

    for i in range(len(decoded)):
        chunk = decoded[i] ^ mask[i % 4]
        bytes_list.append(chunk)
    body = str(bytes_list, encoding='utf-8')
    return body


def send_msg(conn, msg_bytes):
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


def server_socket(host="0.0.0.0", port=8080, max_message_size=1 * 1024 * 1024):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    conn, addr = sock.accept()
    print(conn)
    data = conn.recv(max_message_size)
    headers = get_headers(data)
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

    _startup_dispatcher()
    _startup_send_message_worker(conn)

    while True:
        data = conn.recv(max_message_size)
        receive_queue.put(json.loads(parse_payload(data)))


def _startup_dispatcher():
    def run():
        while True:
            data = receive_queue.get()
            handler = handlers[data['handler']]
            args = data.get('args', None)
            if args:
                dispatchers.submit(handler, *args)
            else:
                dispatchers.submit(handler)

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def _startup_send_message_worker(conn):
    def run():
        while True:
            data = send_queue.get()
            send_msg(conn, data.encode('utf-8'))

    send_thread = threading.Thread(target=run)
    send_thread.setDaemon(True)
    send_thread.start()


def js(handler, *args):
    data = json.dumps({'handler': handler, 'args': args}, ensure_ascii=True)
    send_queue.put(data)


def hello(name):
    js('hello', name)


if __name__ == "__main__":
    handlers['hello'] = hello
    server_socket()
