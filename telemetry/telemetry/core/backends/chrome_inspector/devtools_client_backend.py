# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from telemetry import decorators
from telemetry.core.backends.chrome_inspector import devtools_http


class DevToolsClientBackend(object):
  def __init__(self, devtools_port):
    self._devtools_port = devtools_port
    self._devtools_http = devtools_http.DevToolsHttp(devtools_port)
    self._tracing_backend = None

  # TODO(chrishenry): This is temporarily exposed during DevTools code
  # refactoring. Please do not introduce new usage! crbug.com/423954
  @property
  def devtools_http(self):
    return self._devtools_http

  def IsAlive(self):
    """Whether the DevTools server is available and connectable."""
    try:
      self._devtools_http.Request('', timeout=.1)
    except devtools_http.DevToolsClientConnectionError:
      return False
    else:
      return True

  @decorators.Cache
  def GetChromeBranchNumber(self):
    # Detect version information.
    resp = self._devtools_http.RequestJson('version')
    if 'Protocol-Version' in resp:
      if 'Browser' in resp:
        branch_number_match = re.search(r'Chrome/\d+\.\d+\.(\d+)\.\d+',
                                        resp['Browser'])
      else:
        branch_number_match = re.search(
            r'Chrome/\d+\.\d+\.(\d+)\.\d+ (Mobile )?Safari',
            resp['User-Agent'])

      if branch_number_match:
        branch_number = int(branch_number_match.group(1))
        if branch_number:
          return branch_number

    # Branch number can't be determined, so fail any branch number checks.
    return 0

  # TODO(chrishenry): This is exposed tempoarily during DevTools code
  # refactoring. Instead, we should expose InspectorBackendList or
  # equivalent. crbug.com/423954.
  def ListInspectableContexts(self):
    return self._devtools_http.RequestJson('')
