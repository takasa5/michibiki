import cv2
import numpy as np
import base64
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from PIL import Image
from io import BytesIO
import Constellation
import stardust
import time

data_buffer = {}
app = Flask(__name__)
socketio = SocketIO(app, async_mode="eventlet")
    
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect', namespace='/test')
def test_connect():
    print("connect:"+request.sid)
    #socketio.start_background_task(target=sleeper)
    emit('my_response', {'data': "conecting..."})

@socketio.on('my_event', namespace='/test')
def test_message(message):
    print("event")
    emit('my_response', {'data': message['data']})

@socketio.on('my_image', namespace='/test')
def test_image(message):
    print("recv")
    emit('my_response', {'data': "received image"})
    socketio.sleep(0)
    socketio.start_background_task(background, message)

@socketio.on('data_start', namespace='/test')
def recv_start(message):
    global data_buffer
    data_buffer[request.sid] = message['data']
    emit('require_data', {'index': message['index']+1})

@socketio.on('data_cont', namespace='/test')
def recv_cont(message):
    global data_buffer
    data_buffer[request.sid] += message['data']
    emit('require_data', {'index': message['index']+1})

@socketio.on('data_end', namespace='/test')
def recv_end(message):
    global data_buffer
    print("len:", len(data_buffer))
    #??????????????
    img = readb64(data_buffer[request.sid].split("data:image/jpeg;base64,")[1])
    del data_buffer[request.sid]
    #?????
    # TODO:?????????
    traced_img = stardust.trace(img, Constellation.Sagittarius(), socketio)
    emit('my_response', {'data': "found constellation"})
    socketio.sleep(0)
    #??->base64
    pil_img = Image.fromarray(cv2.cvtColor(traced_img, cv2.COLOR_BGR2RGB))
    sbuf = BytesIO()
    pil_img.save(sbuf, format='JPEG')
    sbuf = sbuf.getvalue()
    encode_img = base64.b64encode(sbuf)

    emit('return_image', {'data': "data:image/jpeg;base64,"+encode_img.decode("utf-8")})
    print("finish!")

def readb64(b64_str):
    sbuf = BytesIO()
    sbuf.write(base64.b64decode(b64_str))
    pimg = Image.open(sbuf)
    cv2img = np.asarray(pimg)
    #RGB->BGR
    return cv2img[:,:,::-1].copy()

if __name__ == '__main__':
    socketio.run(app, debug=True)
