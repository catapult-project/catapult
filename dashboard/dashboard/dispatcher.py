"""Dispatches requests to RequestHandler classes."""

import webapp2

from dashboard import ip_whitelist
from dashboard import main

_ROUTING_TABLE = [
     ('/ip_whitelist', main.IpWhitelistHandler),
     ('/', main.MainHandler),
]

app = webapp2.WSGIApplication(_ROUTING_TABLE, debug=True)
