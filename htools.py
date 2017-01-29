import subprocess
import re


def hbal(cluster_name):

    cluster_info_pattern = r"^Loaded (\d+) nodes, (\d+) instances$"
    score_info_pattern = r"^Cluster score improved from (\d*\.\d+) to (\d*\.\d+)$"
    hbal_steps_pattern = r"^Solution length=(\d+)$"

    hbal_info = {}
    hbal_cmd = "hbal -m " + cluster_name
    hbal_output = subprocess.Popen(hbal_cmd, shell=True, stdout=subprocess.PIPE)
    hbal_text = hbal_output.communicate()[0].split('\n')
    for hbal_line in hbal_text:
        cluster_info_match = re.match( cluster_info_pattern, hbal_line)
        if cluster_info_match:
            hbal_info["node_number"] = cluster_info_match.group(1)
            hbal_info["instance_number"] = cluster_info_match.group(2)
        score_info_match = re.match( score_info_pattern, hbal_line)
        if score_info_match:
            hbal_info["current_score"] = score_info_match.group(1)
            hbal_info["target_score"] = score_info_match.group(2)
        hbal_steps_match = re.match( hbal_steps_pattern, hbal_line)
        if hbal_steps_match:
            hbal_info["hbal_steps_number"] = hbal_steps_match.group(1)
    return hbal_info
