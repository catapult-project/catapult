# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Dispatches requests to RequestHandler classes."""

import webapp2

from dashboard import alerts
from dashboard import ip_whitelist
from dashboard import main
from dashboard import mr

# Importing graph_data registers the ndb Model classes with NDB
# so that they can be used in utils.py.
from dashboard.models import graph_data

_ROUTING_TABLE = [
     ('/alerts', alerts.AlertsHandler),
     ('/ip_whitelist', ip_whitelist.IpWhitelistHandler),
     ('/', main.MainHandler),
     ('/mr_deprecate_tests', mr.MRDeprecateTestsHandler),
]

app = webapp2.WSGIApplication(_ROUTING_TABLE, debug=True)
