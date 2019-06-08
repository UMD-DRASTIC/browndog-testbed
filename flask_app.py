import os
import logging
import logging.config
from logging import handlers
import json
import requests
from flask import Flask, jsonify, request, session, g, redirect, url_for, render_template, make_response, Response
from flask_cors import CORS


app = Flask(__name__)
cors = CORS(app)
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

SIM_FILTER_TERMS = [
    "backend_nodes",
    "frontend_nodes",
    "testworker_nodes",
    "simulation",
    "testbed_commit",
    "testbed_git_url",
    "subject_commit",
    "subject_git_url",
    "subject_docker_name",
    "subject_docker_tag",
    "jms_use_queue",
    "cassandra_replication_factor",
    "cassandra_binary_read_consistency",
    "cassandra_binary_write_consistency",
    "cassandra_rdf_write_consistency",
    "cassandra_rdf_read_consistency",
    "cassandra_max_chunk_size"]


@app.errorhandler(404)
def page_not_found(error):
    return 'This route does not exist {}'.format(request.url), 404


@app.route('/')
def welcome():
    response = make_response(render_template('index.html'))
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:9200'
    return response


@app.route('/bytes-in-format')
def bytes_in_format():
    return format_report(inbytes=True)


@app.route('/files-in-format')
def format_report(inbytes=False):
    inventory_url = "{0}/ciber-file-extensions/_search".format(elasticsearch_url)
    sort_field = 'bytes_in_format.value' if inbytes else 'doc_count'
    q_extensions = '''{{
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


@app.route('/sims', methods=['POST', 'GET'])
def sims():
    app.logger.info("starting")
    sims = None
    if request.method == 'POST' and request.json is not None and len(request.json) > 0:
        app.logger.info("get terms in POST JSON:\n"+json.dumps(request.json, indent=2))
        terms = {}
        for name in request.json:
            if name in SIM_FILTER_TERMS:
                terms[name + '.keyword'] = request.json[name]
        app.logger.info(json.dumps(terms, indent=2))
        sims = get_filtered_sims(terms)
        app.logger.info("sims: "+str(sims) )
    url = "{0}/gatling-ldp-%2A/_search".format(elasticsearch_url)
    payload = '''{
  "size": 0,
  "aggs": {
    "simulations": {
        "terms": {
            "field": "_index",
            "size": 50,
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
            "start": {"min": {"field": "@timestamp"} }
        }
      }
    }
}'''
    req_body = json.loads(payload)

    # Add aggregations for each sim query term
    for t in SIM_FILTER_TERMS:
        req_body['aggs']['simulations']['aggs'][t] = {"terms": {"field": t +'.keyword'} }
    if sims is not None:
        if len(sims) == 0:
            # No sims match the query terms.
            return jsonify([])
        else:
            req_body['query'] = { 'terms': { '_index' : sims } }
    app.logger.info(json.dumps(req_body, indent=2))
    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache"
        }
    response = requests.request("POST", url, data=json.dumps(req_body), headers=headers).json()
    # app.logger.info(json.dumps(response, indent=2))
    result = []
    try:
        result = response['aggregations']['simulations']['buckets']
    except KeyError:
        app.logger.warn("Got the keyerror")
        pass
    return jsonify(result)


def get_filtered_sims(terms):
    url = "{0}/gatling-ldp-%2A/_search".format(elasticsearch_url)
    q = { 'size': 100, '_source': ['_index'], 'query': { 'bool': { 'filter': [] } } }
    for t in terms:
        clause = { 'term': { t: terms[t] }}
        q['query']['bool']['filter'].append(clause)
    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache"
        }
    app.logger.info(json.dumps(q, indent=2))
    response = requests.request("POST", url, data=json.dumps(q), headers=headers).json()
    result = []
    try:
        for hit in response['hits']['hits']:
            result.append(hit['_index'])
    except KeyError:
        pass
    return result


if __name__ == '__main__':
    app.run("0.0.0.0", processes=5)
