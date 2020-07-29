# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for request handlers that display charts."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json

from dashboard.common import request_handler
from dashboard.common import namespaced_stored_object

# The revision info (stored in datastore) is a dict mapping of revision type,
# which should be a string starting with "r_", to a dict of properties for
# that revision, including "name" and "url".
REVISION_INFO_KEY = 'revision_info'


class ChartHandler(request_handler.RequestHandler):
  """Base class for requests which display a chart."""

  def RenderHtml(self, template_file, template_values, status=200):
    """Fills in template values for pages that show charts."""
    template_values.update(self._GetChartValues())
    template_values['revision_info'] = json.dumps(
        template_values['revision_info'])
    return super(ChartHandler, self).RenderHtml(
        template_file, template_values, status)

  def GetDynamicVariables(self, template_values, request_path=None):
    template_values.update(self._GetChartValues())
    super(ChartHandler, self).GetDynamicVariables(
        template_values, request_path)

  def _GetChartValues(self):
    return {
        'revision_info': namespaced_stored_object.Get(REVISION_INFO_KEY) or {},
    }
