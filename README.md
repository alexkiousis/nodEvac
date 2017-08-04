# nodEvac

---

A Ganeti cluster node evacuation tool. 

The main idea of this tool is to give someone (more specifically a technician)  
a Web UI to evacuate a node from a Ganeti cluser and poweroff the machine   
without requiring SSH access to the hosts.

Written in Flask and uses Celery for async tasks (with Redis as a broker).


## Assumptions

This project makes the following assumptions:

* You have one or more Ganeti clusters
* You have a Rapi user for each of the clusters and the RAPI port is accesible
* You have access to the IPMI interface of each machine 
in order to issue poweroff/on commands
* The hosts are pingable from the server the project runs
in order to detect host status
* Alls hosts share the same IPMI credentials
* The IPMI hostname is assigned on each node with an ipmi:<FQDN> Ganeti tag
* Any non mirrored VM on the cluster (file,plain templates) will be shutdown 
  during evacuation (not implemented yet)


## Limitations

Current limitations (mainly Ganeti's) that I would like to find a workaround for:

* You can't failover/demote a master node (this is by design)
  * This means we can't shutdown a master node
* You can't properly readd a node to the cluster - we fallback to modify 
  --offline no which is not clean


## Instalation

* Clone the project
```
git clone https://github.com/alexkiousis/nodEvac.git
```
* Create a virtualenv
```
virtualenv .venv
source .venv/bin/activate
```
* Install requirements
```
pip install -r requirements.txt
```
* Install redis
```
apt-get install redis-server
```
* Install ipmitool
```
apt-get install ipmitool
```
* Create a config file named cluster_config.py in the root of the repository with the Ganeti credentials
  * See [ganeti_utils.py](ganeti_utils.py) for more clear instructions
* Run celery
```
celery -A tasks.celery_app_worker --log-level=info -E --concurrency=10
```
* Run nodEvac
```
./nodEvac.py
```


## Dependencies

Full dependency state is in the [requirements.txt](requirements.txt) file.

These are the explanations for the root dependencies:

* Flask: the backend software the project runs on
* Celery: a worker queue for running asyncronus jobs 
  * all ganeti jobs and ipmitool commands run through celery
* redis: library to communicate with a redis instance
  * used as a broker for celery and for job state caching for the application
* pycurl and simplejson: are dependencies for the Ganeti rapi client library in contrib
