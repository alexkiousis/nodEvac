"""
Celery Tasks for nodEvac
"""
import subprocess
import time
import re

from celery import Celery
from celery.decorators import task

from ganeti_utils import cluster_connection, get_node_info,\
    get_cluster_info, GANETI_CLUSTER
from ipmi import get_ipmi_info
from ici import sched_downtime 

celery_app = Celery('nodevac', broker="redis://localhost:6379/0")
celery_app.conf.result_backend = "redis://localhost:6379/0"

@task(bind=True)
def evacuate_node_task(self, node_name, cluster_name):
    """ Handles the tasks needed to evacuate a Ganeti node."""
    print("Begin node evacuation task for node " + node_name)
    evac_status = {}
    cluster_conn = cluster_connection(cluster_name)
    node_info = get_node_info(node_name, cluster_name)
    evac_status["role"] = node_info["role"]
    evac_status["pinst_cnt"] = node_info["pinst_cnt"]
    evac_status["inst_done"] = 0
    print(evac_status)
    self.update_state(state='E_STARTED',
                      meta={'status': evac_status})

    if evac_status["role"] != "Drained":
        print('Current role is :' + evac_status["role"] + ". Draining...")
        node_drain_job = cluster_conn.SetNodeRole(node_name, "drained")
        node_drain_job_status = cluster_conn.WaitForJobCompletion(node_drain_job)
        if node_drain_job_status:
            evac_status["role"] = "Drained"
            print("Node drained.")
    self.update_state(state='E_DRAINED',
                      meta={'status': evac_status})

    print("Spawning migrate jobs...")
    print ("Running VMs:" + str(node_info["pinst_list"]))
    # This dict will hold the task
    # current status of each task
    migration_progress = {}
    for instance in node_info["pinst_list"]:
        jobid = migrate_instance_task.apply_async(kwargs={
            'instance_name': instance,
            'cluster_name': cluster_name
        })
        migration_progress[instance] = {}
        migration_progress[instance]["task_id"] = str(jobid)
        self.update_state(state='E_MIGRATING',
                          meta={'status': evac_status,
                                'progress': migration_progress
                               }
                         )
        while jobid.state in ["PENDING", "JSTARTED", "JPENDING"]:
            time.sleep(10)
            migration_progress[instance]["task_state"] = jobid.state
            migration_progress[instance]["task_status"] = jobid.info
            self.update_state(state='E_MIGRATING',
                              meta={'status': evac_status,
                                    'progress': migration_progress
                                   }
                             )
        evac_status["inst_done"] += 1
        print("VMs done:" + str(evac_status["inst_done"]) +
              "/" + str(evac_status["pinst_cnt"]))
        self.update_state(state='E_MIGRATING',
                          meta={'status': evac_status,
                                'progress': migration_progress
                               }
                         )
    print("Node emptied. Continuing.")
    node_offline_job = cluster_conn.SetNodeRole(node_name, "offline")
    node_offline_job_status = cluster_conn.WaitForJobCompletion(node_drain_job)
    if node_offline_job_status:
        evac_status["role"] = "Offline"
        print("Node drained.")
    self.update_state(state='E_OFFLINING',
                      meta={'status': evac_status,
                            'progress': migration_progress
                           }
                     )
    return {'status': evac_status, 'progress': migration_progress}

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


@task(bind=True)
def shutdown_node_task(self, node_name, cluster_name):
    """
    After doing the nessecary checks, sends an ipmi command to shutdown
    and loops until it's off
    """
    cluster_conn = cluster_connection(cluster_name)
    node_info = cluster_conn.GetNode(node_name)

    if node_info["pinst_cnt"] != 0:
        return 'Node is not empty. Refusing to proceed.'

    ipmi_info = get_ipmi_info(node_name, cluster_name)

    node_drain_job = cluster_conn.SetNodeRole(node_name, "offline")
    cluster_conn.WaitForJobCompletion(node_drain_job)

    ipmi_status_cmd = ("ipmitool -H " + ipmi_info["host"] + " -U " +
                       ipmi_info["username"] + " -I lanplus -P " +
                       ipmi_info["password"] + " power status")
    ipmi_shut_cmd = ("ipmitool -H " + ipmi_info["host"] + " -U " +
                     ipmi_info["username"] + " -I lanplus -P " +
                     ipmi_info["password"] + " power soft")
    ipmi_status_regex = "Chassis Power is ([a-z]*)\\n"

    print("Sending downtime command for host.")
    # Send downtime command for 2h
    sched_downtime(node_name, '3600')

    message = "Sending shutdown signal to host " + ipmi_info["host"] + "."
    try:
        subprocess.check_output(ipmi_shut_cmd, shell=True)
        self.update_state(state='SHUT_SENT', meta={'message': message})
    except subprocess.CalledProcessError as ipmitool_error:
        print(ipmitool_error)

    while True:
        ipmi_status_out = subprocess.check_output(ipmi_status_cmd, shell=True)
        ipmi_status = re.match(ipmi_status_regex, ipmi_status_out).group(1)
        if ipmi_status == "on" or ipmi_status == "soft":
            print("IPMI is still powered on." + ipmi_status_out)
            time.sleep(6)
        else:
            print("IPMI power if off.")
            break
    return "IPMI host is down."


@task()
def startup_node_task(node_name, cluster_name):
    """
    Send ipmi command to start a hardware node and do a ping check until we
    can readd the node to the cluster
    """
    cluster_conn = cluster_connection(cluster_name)
    node_info = cluster_conn.GetNode(node_name)
    ipmi_info = get_ipmi_info(node_name, cluster_name)

    ping_cmd = "ping -c 1 -w 1 " + node_name
    print("Sending wakeup signal to host " + ipmi_info["host"] + ".")
    ipmi_up_cmd = ("ipmitool -H " + ipmi_info["host"] + " -U " +
                   ipmi_info["username"] + " -I lanplus -P " +
                   ipmi_info["password"] + " power up")
    print(ipmi_up_cmd)
    ipmi_up_out = subprocess.check_output(ipmi_up_cmd, shell=True)
    print(ipmi_up_out)
    while True:
        try:
            time.sleep(20)
            subprocess.check_output(ping_cmd, shell=True)
        except subprocess.CalledProcessError:
            print("No response yet. Wating 20 sec and retrying.")
        else:
            print("Ping check sucessful. Host is online.")
            break

    time.sleep(20)
    node_readd_job = cluster_conn.SetNodeRole(node_name, "regular")
    node_readd_job_status = cluster_conn.WaitForJobCompletion(node_readd_job)

    return "Host is up."
