from contrib.ganeti_client import GanetiApiError, GanetiRapiClient, GenericCurlConfig

ganeti_node_role_desc = {
        'N': 'Normal',
        'R': "Regular",
        'C': 'Master Candidate',
        'D': 'Drained',
        'O': 'Offline',
        'M': 'Master',
}

GANETI_CLUSTER = {
#  Example cluster config
#  "<cluster_fqdn>": {
#    "username": "<rapi_username>",
#    "password": "<rapi_password>",
#  },
    }

def cluster_connection(cluster_name):
    # TODO this returns KeyError if cluster_name doesn't exist in dict
    cluster_info = GANETI_CLUSTER[cluster_name]
    cluster_conn = GanetiRapiClient(cluster_name,
            username = cluster_info["username"],
            password = cluster_info["password"]
            )
    return cluster_conn

def get_node_info(node, cluster):
    cluster_conn = cluster_connection(cluster)
    node_info = cluster_conn.GetNode(node)
    # Expand the role value from a single letter designation to human readable format
    node_info["role"] = ganeti_node_role_desc[node_info['role']]
    return node_info

def get_cluster_info(cluster):
    cluster_conn = cluster_connection(cluster)
    cluster_info = cluster_conn.GetInfo(cluster)
    nodes_list = cluster_conn.GetNodes(bulk=True)
    cluster_info["nodes"] = nodes_list
    return cluster_info

def evacuate_node(node):
    """Helper functon to evacuate a node from VMs and offline it."""
    # TODO(alexk): handle shutdown non-migratable vms 
    if node == None:
        sys.exit("You must select a node.")
    for cluster in Cluster.objects.filter(disabled=False):
        for node_name in cluster._client.GetNodes():
            if node_name == node:
                cl = cluster
    # TODO: handle node not present in clusters
    try:
        cl._client.GetNode(node)
    except GanetiApiError:
        sys.exit("There is no node " + node + " in cluster " + cl.hostname)
    print "Node role is " + cl._client.GetNodeRole(node)
    # TODO(alexk): bail out if node is already offline
    print "Beginning evacuation of node " + node + "." 
    running_vms = cl._client.GetNode(node)['pinst_cnt']
    # TODO: convert to while loop and figure a way to bailout when it gets stuck
    if running_vms != 0:
        # migrate_job = cl._client.MigrateNode(node)
        # iterate on vms in order to not lock the queue
        vmlist = cl._client.GetNode(node)['pinst_list']
        print vmlist
        for vm in vmlist:
            # TODO(alexk): handle non migratable VMs
            if cl._client.GetInstance(vm)['disk_template'] in ["diskless","file","plain"]: 
                # TODO(alexk): handle vm already being down
                job = cl._client.ShutdownInstance(vm) 
                print "Can't migrate VM. Shutting down " + vm + "." 
            else:
                # now we can migrate
                job = cl._client.MigrateInstance(vm)
                print "Migrating VM " + vm + " [ " + str(job) + "]" 
            cl._client.WaitForJobCompletion(job)
            # TODO(alexk): Somehow handle stuck migration jobs
            if cl._client.GetJobStatus(job)['opstatus'][0] != "success":
                sys.exit("VM migration job n." + str(job) + " failed.")
            else:
                print "Done."
    else:
        # nothing to do ...
        print("No running VMs.")
    offline_job = cl._client.SetNodeRole(node,'offline')
    offline_status = cl._client.WaitForJobCompletion(offline_job)
    if offline_status:
        print "Node if offline. You can close it now."
    else:
        print "There was a problem with offlining the node."

    print "node role: " + cl._client.GetNodeRole(node)
    print "running vms: " + str(cl._client.GetNode(node)['pinst_cnt'])
