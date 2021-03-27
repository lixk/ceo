# eui
a fast and simple micro-framework for small browser-based applications

### example
server:
```python
import eui
import time


def get_time():
    return str(time.time())


service = {'get_time': get_time}

eui.run(service, static_dir='web/')

```
UI
```html
<!DOCTYPE html>
<html>
<head>
  <script src="eui.js"></script>
</head>
<body>
<script>
eui.run('get_time', {}, function(data){
	    console.log(data);
	  });
</script>
</body>
</html>

```
