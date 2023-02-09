# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Dispatches requests to request handler classes."""

from flask import Flask, request as flask_request, make_response
import logging

import google.cloud.logging
try:
  import googleclouddebugger
  googleclouddebugger.enable(breakpoint_enable_canary=True)
except ImportError:
  pass

google.cloud.logging.Client().setup_logging(log_level=logging.DEBUG)

APP = Flask(__name__)


@APP.route('/')
def DummyHandler():
  return make_response('welcome')

if __name__ == '__main__':
  # This is used when running locally only.
  app.run(host='127.0.0.1', port=8080, debug=True)
