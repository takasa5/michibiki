import cv2
import numpy as np
import base64
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from PIL import Image
from io import BytesIO
import Constellation
import stardust

app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect', namespace='/test')
def test_connect():
    print("connect")
    emit('my_response', {'data': 'Connected!'})

@socketio.on('my_ping', namespace='/test')
def ping_pong():
    emit('my_pong')

@socketio.on('my_event', namespace='/test')
def test_message(message):
    print("event")
    emit('my_response', {'data': message['data']})

@socketio.on('my_image', namespace='/test')
def test_image(message):
    print("recv")
    emit('my_response', {'data': "received data"})
    img = readb64(message['data'].split("data:image/jpeg;base64,")[1])
    
    traced_img = stardust.trace(img, Constellation.Sagittarius())
    
    pil_img = Image.fromarray(cv2.cvtColor(traced_img, cv2.COLOR_BGR2RGB))
    sbuf = BytesIO()
    pil_img.save(sbuf, format='JPEG')
    sbuf = sbuf.getvalue()
    encode_img = base64.b64encode(sbuf)

    emit('return_image', {'data': "data:image/jpeg;base64,"+encode_img.decode("utf-8")})

def readb64(b64_str):
    sbuf = BytesIO()
    sbuf.write(base64.b64decode(b64_str))
    pimg = Image.open(sbuf)
    cv2img = np.asarray(pimg)
    #RGB->BGR
    return cv2img[:,:,::-1].copy()

if __name__ == '__main__':
    socketio.run(app, debug=True)
