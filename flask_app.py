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
grafana_url = os.getenv('GRAFANA_URL', default='http://localhost:3000')
grafana_authz_token = os.getenv("GRAFANA_AUTHZ_TOKEN")
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


@app.route('/list_snapshots')
def list_snapshots():
    url = "{0}/api/dashboard/snapshots".format(grafana_url)
    headers = {
        'Accept': 'application/json',
        'Authorization': grafana_authz_token
    }
    return jsonify(requests.request("GET", url, headers=headers).json())


@app.route('/recent_sims')
def recent_sims():
    url = "{0}/gatling-ldp-%2A/_search".format(elasticsearch_url)
    payload = '''
{
  "size": 0,
    "aggs": {
      "simulations": {
        "terms": {
            "field": "_index",
            "size": 10,
            "order": {
                "start": "desc"
            }
        },
        "aggs": {
            "Requests": {
                "filter": {"type": {"value": "REQUEST"} },
                "aggs": {
                    "last_ts": {"max": {"field": "@timestamp"} },
                    "first_ts": {"min": {"field": "@timestamp"} },
                    "req_duration_stats" : { "stats" : { "field" : "duration" } },
                    "status": { "terms": { "field": "okay" } }
                }
            },
            "sim_class": {"terms": {"field": "simulationClass.keyword"} },
            "start": {"min": {"field": "@timestamp"} },
            "subject_docker_name": {"terms": {"field": "subject_docker_name.keyword"} },
            "subject_commit": {"terms": {"field": "subject_commit.keyword"} },
            "subject_docker_tag": {"terms": {"field": "subject_docker_tag.keyword"} },
            "frontend_nodes": {"terms": {"field": "frontend_nodes.keyword"} },
            "backend_nodes": {"terms": {"field": "backend_nodes.keyword"} },
            "testworker_nodes": {"terms": {"field": "testworker_nodes.keyword"} }
        }
      }
    }
}
    '''
    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache"
        }
    response = requests.request("POST", url, data=payload, headers=headers).json()
    result = []
    try:
        result = response['aggregations']['simulations']['buckets']
    except KeyError:
        pass
    return jsonify(result)


if __name__ == '__main__':
    app.run("0.0.0.0", processes=5)
