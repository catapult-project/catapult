# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from flask import Flask

from dashboard.skia_bridge.application.perf_api import query_anomalies
from dashboard.skia_bridge.application import health_checks


def Create():
  app = Flask(__name__)
  app.register_blueprint(health_checks.blueprint, url_prefix='/')
  app.register_blueprint(query_anomalies.blueprint, url_prefix='/anomalies')
  return app
