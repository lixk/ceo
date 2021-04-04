import eui


def callback():
    import webbrowser
    webbrowser.open('index.html')


eui.start(startup_callback=callback)
