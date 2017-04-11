#!/usr/bin/env python
"""
A Flask webapp that handles Ganeti Instance migrations as Celery Tasks
"""
from flask import Flask, request, render_template, url_for, jsonify
import redis

from ganeti_utils import get_node_info, get_cluster_info,\
        GANETI_CLUSTER
from tasks import celery_app, migrate_instance_task, evacuate_node_task,\
        shutdown_node_task, startup_node_task

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    """ list all available clusters and search bar"""
    return render_template('index.html', ganeti_clusters=GANETI_CLUSTER.keys())

@flask_app.route('/cluster/<cluster_name>')
def ganeti_cluster_view(cluster_name):
    if cluster_name in GANETI_CLUSTER.keys():
        cluster_info = get_cluster_info(cluster_name)
        return render_template('cluster.html', cluster_info=cluster_info)

@flask_app.route('/<cluster_name>/<node_name>')
def ganeti_node_view(node_name, cluster_name):
    """Ganeti Node view. Triggers evacuation tasks."""
    node_info = get_node_info(node_name, cluster_name)
    return render_template('node.html',
                           node_name=node_name,
                           cluster_name=cluster_name,
                           node_info=node_info)


@flask_app.route('/migrate', methods=['POST'])
def migrate_instance():
    """
    Triggers a task for instance migration.
    Return a JSON view with the URL get the task status.
    """
    task = migrate_instance_task.apply_async(kwargs={
        'instance_name': request.form['instance_name'],
        'cluster_name': request.form['cluster_name']
    })
    return jsonify({}), 202, {
        'Location': url_for('taskstatus', task_id=task.id)}

@flask_app.route('/evacuate_node', methods=['POST'])
def evacuate_node():
    """
    Triggers a task for node evacuation.
    Return a JSON view with the URL to get the task status.
    """
    view_key = ('nodEvac:evacuate_node:' + request.form["cluster_name"] + ":"\
            + request.form["node_name"])
    redis_conn = redis.StrictRedis()
    task_id = redis_conn.get(view_key)
    # if empty there is no running task, so trigger one
    if task_id == '' or task_id is None:
        task = evacuate_node_task.apply_async(kwargs={
            'node_name': request.form['node_name'],
            'cluster_name': request.form['cluster_name']
        })
        redis_conn.set(view_key, task.id)
        task_id = task.id
    # else return the running id
    return jsonify({}), 202, {
        'Location': url_for('evacjob_taskstatus', task_id=task_id)}

@flask_app.route('/shutdown_node', methods=['POST'])
def shutdown_node():
    """
    Triggers a task to shutdown the specified hardware node.
    Return a JSON view with the URL get the task status.
    """
    task = shutdown_node_task.apply_async(kwargs={
        'node_name': request.form['node_name'],
        'cluster_name': request.form['cluster_name']
    })
    return jsonify({}), 202, {
        'Location': url_for('shutdownjob_taskstatus', task_id=task.id)}

@flask_app.route('/startup_node', methods=['POST'])
def startup_node():
    """
    Triggers a task to startup the specified hardware node.
    Return a JSON view with the URL to get the task status.
    """
    task = startup_node_task.apply_async(kwargs={
        'node_name': request.form['node_name'],
        'cluster_name': request.form['cluster_name']
    })
    return jsonify({}), 202, {
        'Location': url_for('startup_taskstatus', task_id=task.id)}



@flask_app.route('/status/<task_id>')
def taskstatus(task_id):
    """
    Parses the status for th Celery job requested and returns a JSON view with
    relevant info.
    """
    task = migrate_instance_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'percent': task.info.get('percent', ''),
            'status': task.info.get('status', ''),
            'job_id': task.info.get('job_id', ''),
            'job_status': task.info.get('job_status', ''),
            'job_details': task.info.get('job_details', ''),
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        # something went wrong in the background job
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)

@flask_app.route('/evac_status/<task_id>')
def evacjob_taskstatus(task_id):
    """
    Parses the status for a evacuate_node_task Celery job requested and
    returns a JSON view with relevant info.
    """
    task = evacuate_node_task.AsyncResult(task_id)
    result = {'result': task.state, 'message': task.info}
    return jsonify(result)

@flask_app.route('/shut_status/<task_id>')
def shutdownjob_taskstatus(task_id):
    """
    Parses the status for a shutdown_node_task Celery job requested and
    returns a JSON view with relevant info.
    """
    task = shutdown_node_task.AsyncResult(task_id)
    result = {'result': task.state, 'message': task.info}
    return jsonify(result)


@flask_app.route('/start_status/<task_id>')
def startup_taskstatus(task_id):
    """
    Parses the status for a startup_node_task Celery job requested and returns
    a JSON view with  relevant info.
    """
    task = startup_node_task.AsyncResult(task_id)
    result = {'result': task.state, 'message': task.info}
    return jsonify(result)

if __name__ == '__main__':
    flask_app.run(host='::')
