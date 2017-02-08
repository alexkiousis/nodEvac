"""Helper functions for Ganeti related operations"""
from contrib.ganeti_client import GanetiRapiClient

# Read cluster credentials from external file (dictionary in python file)
#  Example cluster config
#  "<cluster_fqdn>": {
#    "username": "<rapi_username>",
#    "password": "<rapi_password>",
#  },
from cluster_config import GANETI_CLUSTER

GNTNODE_ROLE_DESC = {
'R': "Regular",
'C': 'Master Candidate',
'D': 'Drained',
'O': 'Offline',
'M': 'Master',
}


def cluster_connection(cluster_name):
    """Establishes a cluster connection.
    Cluster name must be befined, as called, in the GANETI_CLUSTER dict.

    @return: GanetiRapiClient object

    """
    # TODO this returns KeyError if cluster_name doesn't exist in dict
    cluster_info = GANETI_CLUSTER[cluster_name]
    cluster_conn = GanetiRapiClient(cluster_name,
                                    username=cluster_info["username"],
                                    password=cluster_info["password"]
                                   )
    return cluster_conn

def get_node_instances(node, cluster):
    cluster_conn = cluster_connection(cluster)
    node_info = cluster_conn.GetNode(node)
    # Expand the role from a single letter designation to human readable format
    node_info["role"] = GNTNODE_ROLE_DESC[node_info['role']]
    return node_info


def get_node_info(node, cluster):
    """Fetch node info from the specified cluster.

    @return: dict
    """
    cluster_conn = cluster_connection(cluster)
    node_info = cluster_conn.GetNode(node)
    # Expand the role from a single letter designation to human readable format
    node_info["role"] = GNTNODE_ROLE_DESC[node_info['role']]
    return node_info

def get_cluster_info(cluster):
    """ Fetch cluster info from the specified cluster.

    @return: dict
    """
    cluster_conn = cluster_connection(cluster)
    cluster_info = cluster_conn.GetInfo(cluster)
    nodes_list = cluster_conn.GetNodes(bulk=True)
    cluster_info["nodes"] = nodes_list
    return cluster_info
