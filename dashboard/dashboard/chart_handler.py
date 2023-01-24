# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Base class for request handlers that display charts."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import six

from dashboard.common import request_handler
from dashboard import revision_info_client


def RenderHtmlFlask(template_file, template_values, status=200):
  """Fills in template values for pages that show charts."""
  template_values.update(_GetChartValues())
  template_values['revision_info'] = json.dumps(
      template_values['revision_info'])
  return request_handler.RequestHandlerRenderHtml(template_file,
                                                  template_values, status)


def GetDynamicVariablesFlask(template_values, request_path=None):
  template_values['revision_info'] = \
    revision_info_client.GetRevisionInfoConfig()
  request_handler.RequestHandlerGetDynamicVariables(template_values,
                                                    request_path)


def _GetChartValues():
  return {'revision_info': revision_info_client.GetRevisionInfoConfig()}


if six.PY2:

  class ChartHandler(request_handler.RequestHandler):
    """Base class for requests which display a chart."""

    def RenderHtml(self, template_file, template_values, status=200):
      """Fills in template values for pages that show charts."""
      template_values.update(self._GetChartValues())
      template_values['revision_info'] = json.dumps(
          template_values['revision_info'])
      return super().RenderHtml(template_file, template_values, status)

    def GetDynamicVariables(self, template_values, request_path=None):
      template_values.update(self._GetChartValues())
      super().GetDynamicVariables(template_values, request_path)

    def _GetChartValues(self):
      return {'revision_info': revision_info_client.GetRevisionInfoConfig()}
