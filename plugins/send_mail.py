from email.mime.multipart import MIMEMultipart
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from sqlalchemy import create_engine
from datetime import datetime, timedelta
from urllib.parse import unquote
import mysql.connector
import smtplib
import mimetypes
import pandas as pd
import os


def mail_func(**kwargs):
    def get_annex(fileToSend, table_name):
        ctype, encoding = mimetypes.guess_type(fileToSend)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        if maintype == "text":
            fp = open(fileToSend)
            # Note: we should handle calculating the charset
            attachment = MIMEText(fp.read(), _subtype=subtype)
            fp.close()
        elif maintype == "image":
            fp = open(fileToSend, "rb")
            attachment = MIMEImage(fp.read(), _subtype=subtype)
            fp.close()
        elif maintype == "audio":
            fp = open(fileToSend, "rb")
            attachment = MIMEAudio(fp.read(), _subtype=subtype)
            fp.close()
        else:
            fp = open(fileToSend, "rb")
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(fp.read())
            fp.close()
            encoders.encode_base64(attachment)

        attachment.add_header("Content-Disposition", "attachment", filename=table_name)  ####  filename檔名用英文 否則會有未命名附件出現
        return attachment

    def main(**kwargs):
        today = kwargs["timeset"].strftime("%Y-%m-%d")
        emailto = kwargs["emailto"]
        username = "123@123"
        password = "123"

        msg = MIMEMultipart()
        msg["From"] = kwargs["emailfrom"]
        msg["Subject"] = kwargs["subject"]
        # msg.preamble = "do something"
        text = MIMEText(kwargs["text_cont"])
        msg.attach(text)

        mes = kwargs["is_annex"]
        if mes:
            prod_name = kwargs["prod_name"]
            path = kwargs["data_path"]
            for name in prod_name:
                file_name = f"{name}_{today}.xlsx"
                msg.attach(get_annex(path + file_name, file_name))
        else:
            pass

        server = smtplib.SMTP("127.0.0.1:25")
        server.bind(("0.0.0.0", 6677))
        # server.starttls()
        server.login(username, password)
        for user in emailto:
            msg["To"] = user
            server.sendmail(kwargs["emailfrom"], user, msg.as_string())
        server.quit()

    main(**kwargs)
