from threading import Thread
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from time import sleep
from classes.MediaPlayerConfig import MediaPlayerConfig
from classes.MediaPlayer import MediaPlayer
import logging
import pyudev

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


def play_cd(media_player):
  media_player.try_play_cd()
  if media_player.is_running:
    while media_player.is_running:
      for info in iter(media_player.poll_info, None):
        print(info.as_dict())
        socket.emit('media_player_info', info.as_dict())
      sleep(0.2)
    socket.emit('media_player_info', media_player.get_current().as_dict())

play_cd(media_player)

# now check if there are any USB changes (which includes CD insertion)
udev_context = pyudev.Context()
udev_monitor = pyudev.Monitor.from_netlink(udev_context)
udev_monitor.filter_by(subsystem='block')
for device in iter(udev_monitor.poll, None):
  if device.action == 'change' or device.action == 'add':
    sleep(1)
    play_cd(media_player)
