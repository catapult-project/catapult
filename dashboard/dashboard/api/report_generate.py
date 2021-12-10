# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import six

from dashboard.api import api_request_handler
# Module imported for its side effects, to register static report templates.
import dashboard.common.system_health_report  # pylint: disable=unused-import
from dashboard.models import report_template


# pylint: disable=abstract-method
class ReportGenerateHandler(api_request_handler.ApiRequestHandler):

  def _CheckUser(self):
    pass

  def Post(self, *args, **kwargs):
    del args, kwargs  # Unused.
    revisions = self.request.get('revisions', None)
    if revisions is None:
      raise api_request_handler.BadRequestError
    try:
      revisions = [int(r) if r != 'latest' else r for r in revisions.split(',')]
    except ValueError as e:
      six.raise_from(api_request_handler.BadRequestError, e)

    try:
      template_id = int(self.request.get('id'))
    except ValueError as e:
      six.raise_from(api_request_handler.BadRequestError, e)
    try:
      report = report_template.GetReport(template_id, revisions)
    except AssertionError as e:
      # The caller has requested internal-only data but is not authorized.
      six.raise_from(api_request_handler.NotFoundError, e)
    if report is None:
      raise api_request_handler.NotFoundError

    return report
