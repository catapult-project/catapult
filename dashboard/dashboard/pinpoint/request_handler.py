# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Simple Request handler for Pinpoint."""

import os
import webapp2

_STATIC_PYTHON_DIR = os.path.dirname(os.path.dirname(__file__))


class RequestHandler(webapp2.RequestHandler):
  """Base class for requests. Does common template and error handling tasks."""

  def RenderStaticHtml(self, filename):
    filename = os.path.join(_STATIC_PYTHON_DIR, 'pinpoint', 'static', filename)
    contents = open(filename, 'r')
    self.response.out.write(contents.read())
    contents.close()
