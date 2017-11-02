import os
import logging
import logging.config
from logging import handlers
import json
import requests
from flask import Flask, jsonify, request, session, g, redirect, url_for, render_template, Response


app = Flask(__name__)
app.config.from_object(__name__)
app.logger.setLevel(logging.DEBUG)
handler = handlers.RotatingFileHandler(
  os.path.join(app.instance_path, 'flask.log'),
  maxBytes=1024 * 1024 * 100,
  backupCount=20)
app.logger.addHandler(handler)

app.config.update(dict(
    # DATABASE=os.path.join(app.instance_path, 'sqlite3.db'),
    DEBUG=True,
    USERNAME='admin',
    PASSWORD='default',
    SECRET_KEY='INSECURE_DEVELOPMENT_KEY',
    PROPAGATE_EXCEPTIONS=True
))


@app.errorhandler(404)
def page_not_found(error):
    return 'This route does not exist {}'.format(request.url), 404


@app.route('/')
def welcome():
    return render_template('index.html')


if __name__ == '__main__':
    app.run("0.0.0.0", processes=5)
