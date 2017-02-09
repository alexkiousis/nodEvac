#!/usr/bin/env python
"""
A Flask webapp that handles Ganeti Instance migrations as Celery Tasks
"""
from flask import Flask, request, render_template, url_for, jsonify

from ganeti_utils import get_node_info, get_cluster_info,\
        GANETI_CLUSTER
from tasks import celery_app, migrate_instance_task

flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    """ list all available clusters and search bar"""
    return render_template('index.html', ganeti_clusters=GANETI_CLUSTER.keys())

@flask_app.route('/cluster/<cluster_name>')
def ganeti_cluster_view(cluster_name):
    if cluster_name in GANETI_CLUSTER.keys():
        cluster_info = get_cluster_info(cluster_name)
        return render_template('cluster.html', cluster_nam=cluster_name,
                               cluster_info=cluster_info)

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

if __name__ == '__main__':
    flask_app.run(host='::')
