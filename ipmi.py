"""Utils class that handles all IPMI related functions"""
from ganeti_utils import get_node_info

IPMI_USER_HP = "Administrator"
IPMI_USER_FJ = "admin"
IPMI_PASS = ""

def get_ipmi_info(node_name, cluster_name):
    """
    Query a ganeti node and create a dictionary with it's credentials.
    ASSUME: there is a ganeti node tag like ipmi:<FQDN>
    ASSUME: (hardcoded) if fqdn begins with iRMC use IPMI_USER_FJ, else use IPMI_USER_HP
    ASSUME: iRMC fqdn starts with iRMC and iLO starts with ilo
    """
    node_info = get_node_info(node_name, cluster_name)
    node_tags = node_info["tags"]
    ipmi_info = {}
    for tag in node_tags:
        if tag.startswith('ipmi:'):
            # get the fqdn part of the tag - anything after the first :
            # split on :, toss the first part and re-stringify
            ipmi_info["host"] = ":".join(tag.split(':')[-1:])
            if ipmi_info["host"].startswith(('iRMC','irmc')):
                ipmi_info["username"] = IPMI_USER_FJ
            else:
                ipmi_info["username"] = IPMI_USER_HP
            ipmi_info["password"] = IPMI_PASS
            return ipmi_info
