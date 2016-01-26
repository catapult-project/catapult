# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A handler and functions to check whether bisect is supported."""

import re

from dashboard import request_handler

# A set of suites for which we can't do performance bisects.
# This list currently also exists in the front-end code.
_UNBISECTABLE_SUITES = [
    'arc-perf-test',
    'browser_tests',
    'content_browsertests',
    'sizes',
    'v8',
]


class CanBisectHandler(request_handler.RequestHandler):

  def post(self):
    """Checks whether bisect is supported for a test.

    Request parameters:
      test_path: A full test path (Master/bot/benchmark/...)
      start_revision: The start of the bisect revision range.
      end_revision: The end of the bisect revision range.

    Outputs: The string "true" or the string "false".
    """
    can_bisect = (
        IsValidTestForBisect(self.request.get('test_path')) and
        IsValidRevisionForBisect(self.request.get('start_revision')) and
        IsValidRevisionForBisect(self.request.get('end_revision')))
    self.response.write('true' if can_bisect else 'false')


def IsValidTestForBisect(test_path):
  """Checks whether a test is valid for bisect."""
  if not test_path:
    return False
  path_parts = test_path.split('/')
  if len(path_parts) < 3:
    return False
  if path_parts[2] in _UNBISECTABLE_SUITES:
    return False
  if test_path.endswith('/ref') or test_path.endswith('_ref'):
    return False
  return True


def IsValidRevisionForBisect(revision):
  """Checks whether a revision looks like a valid revision for bisect."""
  return _IsGitHash(revision) or re.match(r'^[0-9]{5,7}$', str(revision))


def _IsGitHash(revision):
  """Checks whether the input looks like a SHA1 hash."""
  return re.match(r'[a-fA-F0-9]{40}$', str(revision))
