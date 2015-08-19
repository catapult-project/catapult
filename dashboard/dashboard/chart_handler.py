# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for request handlers that display charts."""

import json

from dashboard import layered_cache
from dashboard import namespaced_stored_object
from dashboard import request_handler

# The revision info (stored in datastore) is a dict mapping of revision type,
# which should be a string starting with "r_", to a dict of properties for
# that revision, including "name" and "url".
_REVISION_INFO_KEY = 'revision_info'


class ChartHandler(request_handler.RequestHandler):
  """Base class for requests which display a chart."""

  def RenderHtml(self, template_file, template_values, status=200):
    """Fills in template values for pages that show charts."""
    revision_info = namespaced_stored_object.Get(_REVISION_INFO_KEY) or {}
    template_values.update({
        'revision_info': json.dumps(revision_info),
        'warning_message': layered_cache.Get('warning_message'),
        'warning_bug': layered_cache.Get('warning_bug'),
    })
    return super(ChartHandler, self).RenderHtml(
        template_file, template_values, status)
