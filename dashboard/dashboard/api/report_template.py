# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from dashboard.api import api_request_handler
from dashboard.models import report_template


class ReportTemplateHandler(api_request_handler.ApiRequestHandler):

  # Do not allow anonymous PutTemplate!

  def PrivilegedPost(self, *_):
    template = json.loads(self.request.get('template'))
    name = self.request.get('name', None)
    owners = self.request.get('owners', None)
    if template is None or name is None or owners is None:
      raise api_request_handler.BadRequestError

    owners = owners.split(',')
    template_id = self.request.get('id', None)
    if template_id is not None:
      try:
        template_id = int(template_id)
      except ValueError:
        raise api_request_handler.BadRequestError
    try:
      report_template.PutTemplate(template_id, name, owners, template)
    except ValueError:
      raise api_request_handler.BadRequestError
    return report_template.List()
