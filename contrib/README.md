contrib
=======

This directory contains the Ganeti RAPI client that is distributed along with 
Ganeti (packaged in Debian as python-ganeti-rapi). It's included in this repo 
in order to use with virtualenv (without site-packages).

The version is 2.15.2. There is a patch that add an allow_failover switch for 
the migrate API call.

Ganeti client lib had dependencies on pycurl and simplejson (installed by the 
project's requirements.txt)
