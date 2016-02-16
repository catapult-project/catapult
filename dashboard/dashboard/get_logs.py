# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URI endpoint for retrieving quick_logger.Log."""

import json
import logging
import re

from dashboard import quick_logger
from dashboard import request_handler


class GetLogsHandler(request_handler.RequestHandler):
  """Handles retrieving logs from quick_logger."""

  def get(self):
    """Shows quick_log_viewer.html."""
    self.RenderHtml('quick_log_viewer.html', {})

  def post(self):
    """Retrieves logs.

    Request parameters:
      log_namespace: Namespace of log to retrieve.
      log_name: Name of log to retrieve.
      log_filter: Regex string to filter logs.
      log_size: Number of logs to get.
      after_timestamp: Get the logs after this timestamp.

    Outputs:
      JSON which contains a list of quick_logger.Log.
    """
    log_namespace = self.request.get('namespace')
    log_name = self.request.get('name')
    log_filter = self.request.get('filter')
    log_size = self.request.get('size')
    after_timestamp = self.request.get('after_timestamp')

    logs = quick_logger.Get(log_namespace, log_name)
    if logs is None:
      logging.warning('Log name %s/%s does not exist.', log_namespace,
                      log_name)
      self.response.out.write('[]')
      return

    if log_filter:
      logs = [l for l in logs if re.match(log_filter, l.message)]
    if after_timestamp:
      after_timestamp = float(after_timestamp)
      logs = [l for l in logs if
              getattr(l, 'timestamp', l.index) > after_timestamp]
    if log_size:
      logs = logs[0:int(log_size)]

    serializable_logs = []
    for log in logs:
      serializable_logs.append({
          'id': getattr(log, 'id', log.index),
          'timestamp': getattr(log, 'timestamp', log.index),
          'message': log.message})
    self.response.out.write(json.dumps(serializable_logs))
