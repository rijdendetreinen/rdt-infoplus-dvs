#!/usr/bin/python

import os, sys
system_status = os.popen("/opt/rdt/infoplus-dvs/dvs-dump.py status/status -q").readline().strip()

if system_status == "'OK'":
    print "OK - No downtime detected"
    sys.exit(0)
elif system_status == "'RECOVERING'":
    print "WARNING - Recovering from downtime"
    sys.exit(1)
elif system_status == "'DOWN'":
    print "CRITICAL - Downtime detected, not recovering"
    sys.exit(2)
else:
    print "UKNOWN"
    sys.exit(3)