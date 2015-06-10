"""Dispatches requests to RequestHandler classes."""

import webapp2

from dashboard import ip_whitelist
from dashboard import main

# Importing Model classes in order to register them with NDB.
from dashboard.models import *  # pylint: disable=wildcard-import

_ROUTING_TABLE = [
     ('/ip_whitelist', ip_whitelist.IpWhitelistHandler),
     ('/', main.MainHandler),
]

app = webapp2.WSGIApplication(_ROUTING_TABLE, debug=True)
