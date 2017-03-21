"""
Taken from ici. Submit a downtime command to icinga through livestatus-service.
"""
import urllib2
import time

# ASSUME: ici targe url is hardcoded for now
MONITORING_URL = "194.177.210.168:1337"

def sched_downtime(hostname, duration):
    cur_time = int( time.time() )
    dest_time = cur_time + int(duration)
    # username is reported on icinga
    user='nodEvac'
    # 0 is flexible, 1 is fixed
    # unless rebooting we should prefer fixed
    type=1

    # livestatus-service doesn't need the first time in brackets just the command
    ici_cmd = ("SCHEDULE_HOST_SVC_DOWNTIME;" + hostname + ";" + str(cur_time) +
               ";" + str(dest_time) + ";" + str(type) + ";0;" + str(duration) +
               ";" + user + ";downtime_by_script")
    cmd_query = "http://" + MONITORING_URL + "/cmd?q=" + urllib2.quote(ici_cmd)
    req = urllib2.urlopen(cmd_query).read()
    if req.rstrip("\n") == "OK":
        return True
    else:
        return False
