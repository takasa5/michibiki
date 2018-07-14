# -*- coding:utf-8 -*-
import cv2
import numpy as np
import base64
import uuid
from flask import (Flask, render_template, request,
    copy_current_request_context, url_for, flash,
    redirect, session)
from flask_socketio import SocketIO, emit
from PIL import Image
from io import BytesIO
import Constellation as cs
from stardust import Stardust
import my_email_sender
import time
import os
import re
import eventlet
from rauth.service import OAuth1Service
from rauth.utils import parse_utf8_qsl
# https://github.com/miguelgrinberg/Flask-SocketIO/issues/193
# work in eventlet 0.17.4 without RecursionError
eventlet.monkey_patch(socket=True, select=True)

SESSIONS = []
IMAGES = {}
CSTL_KEYS = ["sagittarius", "scorpius", "gemini", "taurus", "orion"]
CSTL_NAMES = ["いて座", "さそり座", "ふたご座", "おうし座", "オリオン座"]
CSTL_DATA = [cs.sgr, cs.sco, cs.gem, cs.tau, cs.ori]
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode="eventlet", ping_timeout=25, ping_interval=1)

twitter = OAuth1Service(
    name='twitter',
    consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
    consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authenticate',
    base_url='https://api.twitter.com/1.1/'
    )

@app.route('/')
def index():
    return render_template('index.html', title="みちびき(仮)")

@app.route('/twitter/login/<img_id>')
def login(img_id):
    if img_id not in IMAGES:
        flash("不正なIDです")
        return redirect(url_for('index'))
    session["img_id"] = img_id
    oauth_callback = url_for('authorized', _external=True)
    params = {'oauth_callback': oauth_callback}

    r = twitter.get_raw_request_token(params=params)
    data = parse_utf8_qsl(r.content)
    print(data)

    session['twitter_oauth'] = (data['oauth_token'],
                                data['oauth_token_secret'])
    return redirect(twitter.get_authorize_url(data['oauth_token'], **params))

@app.route('/twitter/authorized')
def authorized():
    print(session)
    request_token, request_token_secret = session.pop('twitter_oauth')
    # check to make sure the user authorized the request
    if not 'oauth_token' in request.args:
        flash('You did not authorize the request')
        return redirect(url_for('index'))

    try:
        creds = {'request_token': request_token,
                'request_token_secret': request_token_secret}
        params = {'oauth_verifier': request.args['oauth_verifier']}
        sess = twitter.get_auth_session(params=params, **creds)
    except Exception as e:
        flash('There was a problem logging into Twitter: ' + str(e))
        return redirect(url_for('index'))
    response = sess.post(
        'https://upload.twitter.com/1.1/media/upload.json',
        data={'media_data': IMAGES[session["img_id"]][0]},
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    ret = sess.post(
        'statuses/update.json', 
        data={'status': 'みちびきを使って' + IMAGES[session["img_id"]][1] + 'を見つけました',
              'media_ids': response.json()['media_id']})
    print(ret)
    # User.get_or_create(verify['screen_name'], verify['id'])
    return redirect(url_for('index'))

@app.route('/send_message')
def send_message_page():
    return render_template('sender.html', title="報告フォーム - みちびき(仮)")

@app.route('/send/<session_id>', methods=["POST"])
def data_send(session_id):
    @copy_current_request_context
    def image_processing(from_client):
        global IMAGES, CSTL_DATA, CSTL_NAMES
        image, cst, session_id = from_client
        #画像読み込み
        img = readb64(image.split("data:image/jpeg;base64,")[1])
        # with app.app_context():
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
        cst_name = CSTL_NAMES[CSTL_DATA.index(cst)]
        img_id = str(uuid.uuid4())
        IMAGES[img_id] = (encode_img.decode('utf-8'), cst_name)
        emit("process_finished", {"img": b64img, "id": img_id}, room=session_id, namespace="/test")
    global SESSIONS
    if session_id not in SESSIONS:
        return "failed"
    image = request.form["image"]
    cstl = request.form["cst"]
    #画像読み込み
    # img = readb64(image.split("data:image/jpeg;base64,")[1])
    # TODO:星景写真かどうかの判定
    for (key, data) in zip(CSTL_KEYS, CSTL_DATA):
        if key in cstl:
            print(key)
            cst = data

    TO_SERVER = [image, cst, session_id]
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