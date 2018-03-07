# -*- coding:utf-8 -*-
import cv2
import numpy as np
import base64
from flask import Flask, render_template, request, copy_current_request_context
from flask_socketio import SocketIO, emit
from PIL import Image
from io import BytesIO
import Constellation
import stardust
import my_email_sender
import time
import os
import re
import eventlet
eventlet.monkey_patch(socket=True, select=True)

data_buffer = {}
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode="eventlet", ping_timeout=25, ping_interval=15)
    
@app.route('/')
def index():
    return render_template('index.html', title="みちびき(仮)")

@app.route('/send_message')
def send_message_page():
    return render_template('sender.html', title="報告フォーム - みちびき(仮)")

@socketio.on('connect', namespace='/test')
def test_connect():
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
    @copy_current_request_context
    def detect_constellation(message):
        global data_buffer
        print("len:", len(data_buffer))
        #画像読み込み
        img = readb64(data_buffer[request.sid].split("data:image/jpeg;base64,")[1])
        del data_buffer[request.sid]
        #星座追跡
        # TODO:星景写真かどうかの判定
        if message["cst"] in ["sagittarius"]:
            cst = Constellation.Sagittarius()
        # ここに他の星座を追加 ていうかもっとスマートにする
        traced_img = stardust.trace(img, cst, socketio)
        emit('my_response', {'data': "found constellation"})
        socketio.sleep(0)
        #画像->base64
        pil_img = Image.fromarray(cv2.cvtColor(traced_img, cv2.COLOR_BGR2RGB))
        sbuf = BytesIO()
        pil_img.save(sbuf, format='JPEG')
        sbuf = sbuf.getvalue()
        encode_img = base64.b64encode(sbuf)

        emit('return_image', {'data': "data:image/jpeg;base64,"+encode_img.decode("utf-8")})
        print("finish!")

    #socketio.start_background_task(target=recv_end, message=message)
    eventlet.spawn(detect_constellation, message=message) #spawnならemitが使える
    # TODO:うえのが終わった時にこちらから送信すればいいのでは。


@socketio.on('content_push', namespace="/test")
def recv_content(message):
    """送信フォームからのメッセージ受信"""
    message["sid"] = request.sid
    # TODO: heroku上からファイルサイズ大きめのものを送信すると
    #       送信は成功するが完了表示がなされない
    #       client側の変換処理に時間がかかるためと思われる
    emit("send_complete")
    socketio.sleep(0)
    socketio.start_background_task(target=background_send, message=message)

def background_send(message):
    if message["file"] is not None:
        splited = re.split("[:;,]", message["file"], 4)
        #splited[1] <- mimetype / splited[3] <- base64 string
        message["mimetype"], message["subtype"] = splited[1].split("/")
        message["file"] = base64.b64decode(splited[3])
    else:
        message["mimetype"], message["subtype"] = None, None
        message["file"] = None
    print("background_send")
    my_email_sender.send_message(my_email_sender.create_message(message))


def readb64(b64_str):
    sbuf = BytesIO()
    sbuf.write(base64.b64decode(b64_str))
    pimg = Image.open(sbuf)
    cv2img = np.asarray(pimg)
    #RGB->BGR
    return cv2img[:,:,::-1].copy()

if __name__ == '__main__':
    socketio.run(app, debug=True)
