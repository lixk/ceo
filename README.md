# eui
a fast and simple micro-framework for small browser-based applications

## example
### Step 1:
create python file, `main.py`:
```python
import eui
import webbrowser
import os


def say_hello(message):
    print('receive message from js:', message)
    eui.js('sayHello', message)


def startup_callback():
    # open UI file in browser
    webbrowser.open(os.getcwd() + '/static/index.html')


handlers = {
    'say_hello': say_hello
}

eui.start(handlers=handlers, startup_callback=startup_callback)

```

### Step 2:
create UI file `index.html` in `static` folder:
```html
<!DOCTYPE HTML>
<html>

<head>
   <meta charset="utf-8">
   <title>eui test</title>
   <script src="eui.js"></script>
   <script type="text/javascript">
      function sendMessage() {
         var message = document.getElementById('message').value;
         eui.py('say_hello', message);
      }

      function sayHello(message) {
         alert('receive message from py: ' + message);
      }

   </script>

</head>

<body>
   <input id="message">
   <button onclick="sendMessage()">Send</button>

</body>

</html>

```

### Step 3:
run `main.py`
snapshot:
![snapshot]()
