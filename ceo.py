import os
import random

import aiohttp_cors
from aiohttp import web

_SERVICES = {}

_JS = """/**
* Usage:
* eui.run('hello', {name:'world'}, function(data){console.log(data)});
*/
window.eui = {
    run: function (functionName, data, successCallback, errorCallback) {
        var data = data || {};
        successCallback = successCallback || function (data) {};
        errorCallback = errorCallback || function (e) {console.error(e)};
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function () {
            if (xhr.readyState == 4) {
                var r = xhr.response;
                if (xhr.status == 200) {
                    successCallback(eval('(' + r + ')'));
                } else {
                    errorCallback(r);
                }
            }
        }
        xhr.open('POST', 'http://localhost:%s/', true);
        xhr.send(JSON.stringify({'function': functionName, 'params': data}));
    }
};
"""


async def _handler(request):
    data = await request.json()
    print(data)
    if 'function' not in data:
        return web.json_response(status=500, text="Arg 'function' is required!")
    function_name = data['function']
    if 'params' not in data:
        return web.json_response(status=500, text="Arg 'params' is required!")
    params = data['params']
    if function_name not in _SERVICES:
        return web.json_response(status=404, text="Service '%s' not found!" % function_name)
    try:
        return web.json_response(_SERVICES[function_name](**params), headers={'Server': 'eui'})
    except Exception as e:
        return web.json_response(status=500, text=str(e))


_app = web.Application()
_cors = aiohttp_cors.setup(_app)
_resource = _cors.add(_app.router.add_resource("/"))
_cors.add(_resource.add_route("POST", _handler), {
    "*": aiohttp_cors.Resoureuiptions(allow_credentials=True, allow_headers='*', allow_methods='*')
})


def _init_eui_js(port, static_dir):
    os.makedirs(static_dir, exist_ok=True)
    with open(static_dir + 'eui.js', 'w') as f:
        f.write(_JS % port)


def run(services, port=None, static_dir='./'):
    if not port:
        port = random.randint(5000, 10000)
    _init_eui_js(port, static_dir)
    _SERVICES.update(services)

    web.run_app(_app, port=port)
