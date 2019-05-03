from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from flask import Flask


def CreateApp(test_config=None):
  """Factory for Flask App configuration."""
  app = Flask(__name__, instance_relative_config=True)

  if test_config:
    pass

  @app.route('/validate', methods=['POST'])
  def Validate():  # pylint: disable=unused-variable
    # TODO(dberris): Implement this!
    return ''

  @app.route('/service-metadata')
  def ServiceMetadata():  # pylint: disable=unused-variable
    # TODO(dberris): Implement this!
    return ''

  return app
