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

elasticsearch_url = os.getenv('ELASTICSEARCH_URL', default='http://localhost:9200')

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


@app.route('/bytes-in-format')
def bytes_in_format():
    return format_report(inbytes=True)


@app.route('/files-in-format')
def format_report(inbytes=False):
    inventory_url = "{0}/ciber-file-extensions/_search".format(elasticsearch_url)
    sort_field = 'bytes_in_format.value' if inbytes else 'doc_count'
    q_extensions = '''
    {{
      "size": 100,
      "_source": [ "mimetype", "key", "doc_count", "bytes_in_format.value" ],
      "query": {{
        "match_all": {{}}
      }},
      "sort": [
        {{ "{0}": "desc" }}
      ]
    }}'''.format(sort_field)
    headers = {'cache-control': "no-cache"}
    response = requests.request("POST", inventory_url, data=q_extensions, headers=headers).json()
    return jsonify(response)


if __name__ == '__main__':
    app.run("0.0.0.0", processes=5)
