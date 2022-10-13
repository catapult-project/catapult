# Copyright 2022 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""oauth2 function wrappers which are used by chromeperf."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import logging
import six

if six.PY2:
  from oauth2client.client import GoogleCredentials
else:
  import google.auth


def GetAppDefaultCredentials(scope=None):
  if six.PY2:
    credentials = GoogleCredentials.get_application_default()
    if scope and credentials.create_scoped_required():
      credentials = credentials.create_scoped(scope)
    return credentials

  try:
    credentials, _ = google.auth.default()
    if scope and credentials.requires_scopes:
      credentials = credentials.with_scopes([scope])
    return credentials
  except google.auth.exceptions.DefaultCredentialsError as e:
    logging.error('Error when getting the application default credentials: %s',
                  str(e))
    return None
