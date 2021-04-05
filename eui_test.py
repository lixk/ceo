import os
import webbrowser

import eui


def say_hello(message):
    print('receive message from js:', message)
    eui.js('sayHello', message)


def startup_callback():
    webbrowser.open(os.getcwd() + '/static/index.html')


handlers = {
    'say_hello': say_hello
}

eui.start(handlers=handlers, startup_callback=startup_callback)
