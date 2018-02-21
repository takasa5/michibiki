import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

ACCOUNT = "michibikireport@gmail.com"
ALIAS = "michibikireport+alias@gmail.com"
PASSWORD = os.environ.get("GOOGLE_PASS", None)

def create_message(message):
    print("create_message")
    msg = MIMEMultipart()
    msg["Subject"] = str(message["sid"])
    msg["From"] = ACCOUNT
    msg["To"] = ALIAS
    msg["Date"] = formatdate(localtime=True)
    
    body = MIMEText(message["content"])
    msg.attach(body)
    
    if message["mimetype"] == "image": #画像
        mj = MIMEImage(message["file"], message["subtype"], filename=message["file_name"])
        mj.add_header("Content-Disposition", "attachment", filename=message["file_name"])
        msg.attach(mj)
    elif message["mimetype"] == "application": #zip
        mj = MIMEApplication(message["file"], message["subtype"], filename=message["file_name"])
        mj.add_header("Content-Disposition", "attachment", filename=message["file_name"])
        msg.attach(mj)
    
    return msg

def send_message(message):
    print("send_message")
    s = smtplib.SMTP_SSL("smtp.gmail.com")
    s.login(ACCOUNT, PASSWORD)

    s.send_message(message)
    s.quit()

    print("finished: {}".format(sys._getframe().f_code.co_name))

if __name__ == "__main__":
    pass