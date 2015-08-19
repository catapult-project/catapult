# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides a web interface for seeing recently added points."""

from dashboard import list_tests
from dashboard import request_handler
from dashboard import utils
from dashboard.models import graph_data

# Number of points to list if no number of points is specified.
_DEFAULT_NUM_POINTS = 100

# Max number of tests to use that match a user-specified pattern.
_MAX_MATCHING_TESTS = 5


class NewPointsHandler(request_handler.RequestHandler):
  """Shows a page with a list of recently added points."""

  def get(self):
    """Gets the page for viewing recently added points.

    Request parameters:
      pattern: A test path pattern with asterisk wildcards (optional).

    Outputs:
      A page showing recently added points.
    """
    # Construct a query for recently added Row entities.
    query = graph_data.Row.query()
    query = query.order(-graph_data.Row.timestamp)

    # If a maximum number of tests was specified, use it; fall back on default.
    try:
      max_tests = int(self.request.get('max_tests', _MAX_MATCHING_TESTS))
    except ValueError:
      max_tests = _MAX_MATCHING_TESTS

    # If a test path pattern was specified, filter the query to include only
    # Row entities that belong to a test that matches the pattern.
    test_pattern = self.request.get('pattern')
    num_originally_matching_tests = 0
    if test_pattern:
      test_paths = list_tests.GetTestsMatchingPattern(
          test_pattern, only_with_rows=True)
      if not test_paths:
        self.RenderHtml('new_points.html', {
            'pattern': test_pattern,
            'error': 'No tests matching pattern: %s' % test_pattern,
        })
        return

      # If test_keys contains too many tests, then this query will exceed a
      # memory limit or time out. So, limit the number of tests and let the
      # user know that this has happened.
      num_originally_matching_tests = len(test_paths)
      if num_originally_matching_tests > max_tests:
        test_paths = test_paths[:max_tests]
      test_keys = map(utils.TestKey, test_paths)
      query = query.filter(graph_data.Row.parent_test.IN(test_keys))

    # If a valid number of points was given, use it. Otherwise use the default.
    try:
      num_points = int(self.request.get('num_points', _DEFAULT_NUM_POINTS))
    except ValueError:
      num_points = _DEFAULT_NUM_POINTS

    # Fetch the Row entities.
    rows = query.fetch(limit=num_points)

    # Make a list of dicts which will be passed to the template.
    row_dicts = []
    for row in rows:
      row_dicts.append({
          'test': utils.TestPath(row.parent_test),
          'added_time': row.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z'),
          'revision': row.revision,
          'value': row.value,
          'error': row.error,
      })

    error_message = ''
    if num_originally_matching_tests > max_tests:
      error_message = ('Pattern originally matched %s tests; only showing '
                       'points from the first %s tests.' %
                       (num_originally_matching_tests, max_tests))

    # Render the template with the row information that was fetched.
    self.RenderHtml('new_points.html', {
        'pattern': test_pattern,
        'num_points': num_points,
        'max_tests': max_tests,
        'rows': row_dicts,
        'error': error_message,
    })
