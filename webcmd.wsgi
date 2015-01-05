#!/usr/bin/python
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/www/webcmd/")
sys.path.insert(0,"/var/www/webcmd/webcmd/")

from webcmd import app as application
application.secret_key = 'Add your secret key'
