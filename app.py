# -*- coding:utf-8 -*-
import cv2
import numpy as np
import base64
from flask import Flask, render_template, request, copy_current_request_context
from flask_socketio import SocketIO, emit
from PIL import Image
from io import BytesIO
import Constellation
from stardust import Stardust
import my_email_sender
import time
import os
import re
import eventlet
eventlet.monkey_patch(socket=True, select=True)

SESSIONS = []
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode="eventlet", ping_timeout=25, ping_interval=1)

@app.route('/')
def index():
    return render_template('index.html', title="みちびき(仮)")

@app.route('/send_message')
def send_message_page():
    return render_template('sender.html', title="報告フォーム - みちびき(仮)")

# 6/19 sid個別ページ
# アクセスさばけなくなるのでbg化とかは必要
@app.route('/send/<session_id>', methods=["POST"])
def data_send(session_id):
    global SESSIONS
    if session_id not in SESSIONS:
        return "failed"
    image = request.form["image"]
    cstl = request.form["cst"]
    #画像読み込み
    img = readb64(image.split("data:image/jpeg;base64,")[1])
    # TODO:星景写真かどうかの判定
    if cstl in ["sagittarius"]:
        cst = Constellation.Sagittarius()

    TO_SERVER = [img, cst, session_id]
    socketio.start_background_task(target=image_processing, from_client=TO_SERVER)
    return "successed"

@socketio.on('connect', namespace='/test')
def test_connect():
    emit('my_response', {'data': "conecting..."})

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

@socketio.on('push_send', namespace="/test")
def on_push():
    global SESSIONS
    if request.sid not in SESSIONS:
        SESSIONS.append(request.sid)
    emit("session_id", {"id": request.sid})

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

def image_processing(from_client):
    global app
    img, cst, session_id = from_client
    with app.app_context():
        # 星座検出
        sd = Stardust(img, socket=socketio, session=session_id)
        sd.draw_line(cst)
        traced_img = sd.get_image()
        # 画像->base64
        pil_img = Image.fromarray(cv2.cvtColor(traced_img, cv2.COLOR_BGR2RGB))
        sbuf = BytesIO()
        pil_img.save(sbuf, format='JPEG')
        sbuf = sbuf.getvalue()
        encode_img = base64.b64encode(sbuf)
        b64img = "data:image/jpeg;base64,"+encode_img.decode('utf-8')
        emit("process_finished", {"img": b64img}, room=session_id, namespace="/test")

def readb64(b64_str):
    sbuf = BytesIO()
    sbuf.write(base64.b64decode(b64_str))
    pimg = Image.open(sbuf)
    cv2img = np.asarray(pimg)
    #RGB->BGR
    return cv2img[:,:,::-1].copy()

if __name__ == '__main__':
    # mp.set_start_method('fork', force=True)
    socketio.run(app, debug=True)