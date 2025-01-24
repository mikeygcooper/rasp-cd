from threading import Thread
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import logging
from classes.MediaPlayerConfig import MediaPlayerConfig

config = MediaPlayerConfig('media_player.conf')

media_player = MediaPlayer(config)


# Web server configuration
app = Flask(__name__, template_folder="web", static_folder="web/static", static_url_path="/static")
app.debug = False
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
socket = SocketIO(app, async_mode='threading')

@app.route('/')
def index():
  return render_template('index.html')

@app.route('/getMediaPlayerInfo')
def info():
  return config['NAME']


# Web server thread starting point
def start_web_server():
  if __name__ == '__main__':
    socket.run(app, config['WEB_IP'], port=config['WEB_PORT'])

# Start web server thread
web_server_thread = Thread(target=start_web_server, args=[])
web_server_thread.deamon = True
web_server_thread.start()
