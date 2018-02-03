#import cv2
import numpy as np
import base64
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from PIL import Image
from io import BytesIO
#import Constellation
#import stardust

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kingofsecretyeahhhhh'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index')

@socketio.on('connect', namespace='/test')
def test_connect():
    print("connect")
    emit('my_response', {'data': 'Connected!'})

@socketio.on('my_event', namespace='/test')
def test_message(message):
    print("event")
    emit('my_response', {'data': message['data']})

@socketio.on('my_image', namespace='/test')
def test_image(message):
    print("recv")
    #emit('my_response', {'data': message['data']})
    #img = readb64(message['data'].split("data:image/jpeg;base64,")[1])
    #stardust.trace(img, Constellation.Sagittarius())
    print("saved")
    emit('my_response', {'data': "traced"})

def readb64(b64_str):
    sbuf = BytesIO()
    sbuf.write(base64.b64decode(b64_str))
    pimg = Image.open(sbuf)
    cv2img = np.asarray(pimg)
    #RGB->BGR
    #return cv2img[:,:,::-1].copy()

if __name__ == '__main__':
    socketio.run(app, debug=True)
