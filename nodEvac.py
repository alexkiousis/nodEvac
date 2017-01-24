#!/usr/bin/env python
"""
A Flask webapp that handles Ganeti Instance migrations as Celery Tasks
"""
from ganeti_utils import cluster_connection, get_node_info

from flask import Flask, request, render_template, url_for, jsonify
from celery import Celery

import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dlasjdlasjda'
app.config['CELERY_BROKEN_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKEN_URL'])
celery.conf.update(app.config)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<cluster_name>/<node_name>')
def ganeti_node_view(node_name, cluster_name):
    node_info = get_node_info(node_name, cluster_name)
    return render_template('node.html', node_name = node_name, cluster_name = cluster_name, node_info = node_info)

@app.route('/migrate', methods=['POST'])
def migrate_instance():
    # TODO: handle Celery not being available
    task = migrate_instance_task.apply_async(kwargs={
        'instance_name': request.form['instance_name'], 
        'cluster_name': request.form['cluster_name']
    } )
    return jsonify({}), 202, {'Location': url_for('taskstatus', task_id=task.id)}

@app.route('/status/<task_id>')
def taskstatus(task_id):
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
            'percent': task.info.get('percent', 100),
            'status': task.info.get('status', ''),
            'job_id': task.info.get('job_id', ''),
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

@celery.task(bind=True)
def migrate_instance_task(self, instance_name, cluster_name):
    """Migrate a Ganeti instance"""
    cluster_conn = cluster_connection(cluster_name)
    migrate_job_id = cluster_conn.MigrateInstance(instance_name, allow_failover=True)

    migrate_job_details = cluster_conn.GetJobStatus(migrate_job_id)
    message = "Job Submitted."
    self.update_state(state='JPENDING',
            meta={'percent': '10', 'job_id': migrate_job_id, 'status': message, 'job_details': migrate_job_details})
    time.sleep(120)

    migrate_job_success = cluster_conn.WaitForJobCompletion(migrate_job_id)
    migrate_job_details = cluster_conn.GetJobStatus(migrate_job_id)
    # Reimplement WaitForJobCompeltion polling function here, in order to fetch
    # complete info instead of just status

    if migrate_job_success:
        message = "Migration Complete!"
    else:
        message = "Migration Failed!"
    return {'percent': 100, "job_id": migrate_job_id, 'status': message, "job_details": migrate_job_details}
 
if __name__ == '__main__':
    app.run(host='0.0.0.0')
