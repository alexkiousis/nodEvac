"""
Celery Tasks for nodEvac
"""
from celery import Celery
from celery.decorators import task

from ganeti_utils import cluster_connection, get_node_info,\
    get_cluster_info, GANETI_CLUSTER

celery_app = Celery('nodevac', broker="redis://localhost:6379/0")
celery_app.conf.result_backend = "redis://localhost:6379/0"

@task(bind=True)
def migrate_instance_task(self, instance_name, cluster_name):
    """Migrate a Ganeti instance"""
    message = "Connecting to cluster..."
    self.update_state(state='JSTARTED',
                      meta={'percent': '10', 'status': message})

    cluster_conn = cluster_connection(cluster_name)
    migrate_job_id = cluster_conn.MigrateInstance(
        instance_name, allow_failover=True)

    migrate_job_details = cluster_conn.GetJobStatus(migrate_job_id)
    message = "Job Submitted."
    job_status = "Pending"
    self.update_state(state='JPENDING',
                      meta={
                          'percent': '20',
                          'job_id': migrate_job_id,
                          'job_status': job_status,
                          'status': message,
                          'job_details': migrate_job_details})

    migrate_job_success = cluster_conn.WaitForJobCompletion(migrate_job_id)
    migrate_job_details = cluster_conn.GetJobStatus(migrate_job_id)

    if migrate_job_success:
        message = "Migration Complete!"
        job_status = "Success"
    else:
        message = "Migration Failed!"
        job_status = "Failure"

    return {
        'percent': 100,
        'job_id': migrate_job_id,
        'job_status': job_status,
        'status': message,
        'job_details': migrate_job_details
        }


@task()
def shutdown_node(node_name, cluster_name):
    """ipmi command to shutdown and loop until it returns off"""
    cluster_conn = cluster_connection(cluster_name)
    node_drain_job = cluster_conn.SetNodeRole(node_name, "offline")
    cluster_conn.WaitForJobCompletion(node_drain_job)

@task()
def startup_node(node_name, cluster_name):
    """
    Send ipmi command to start a hardware node and do a ping check until we
    can readd the node to the cluster
    """
    cluster_conn = cluster_connection(cluster_name)
    node_readd_job = cluster_conn.SetNodeRole(node_name, "regular")
    node_readd_job_status = cluster_conn.WaitForJobCompletion(node_readd_job)
    while node_readd_job_status == False:
        node_readd_job = cluster_conn.SetNodeRole(node_name, "regular")
        node_readd_job_status = cluster_conn.WaitForJobCompletion(node_readd_job)
