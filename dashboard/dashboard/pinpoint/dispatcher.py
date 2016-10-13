# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Dispatches requests to request handler classes."""

import webapp2

from dashboard.pinpoint.handlers import job
from dashboard.pinpoint.handlers import new
from dashboard.pinpoint.handlers import run


_URL_MAPPING = [
    (r'/job/(\w+)', job.JobHandler),
    (r'/new', new.NewHandler),
    (r'/run/(\w+)', run.RunHandler),
]

APP = webapp2.WSGIApplication(_URL_MAPPING, debug=False)
