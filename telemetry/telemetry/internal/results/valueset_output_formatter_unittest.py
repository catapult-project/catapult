# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import tempfile
import unittest

from telemetry.internal.results import valueset_output_formatter
from telemetry.internal.results import page_test_results


class ValueSetOutputFormatterTest(unittest.TestCase):

  def setUp(self):
    self.output_file_path = tempfile.mkstemp()[1]

  def tearDown(self):
    try:
      os.remove(self.output_file_path)
    except OSError:
      pass

  def test_basic_summary(self):
    sample = {
        'name': 'a',
        'guid': '42',
        'description': 'desc',
        'important': False,
        'diagnostics': [],
        'type': 'numeric',
        'numeric': {
            'unit': 'n%',
            'type': 'scalar',
            'value': 42
        }
    }

    results = page_test_results.PageTestResults()
    results.value_set.extend([sample])

    with open(self.output_file_path, 'w') as output_file:
      formatter = valueset_output_formatter.ValueSetOutputFormatter(output_file)
      formatter.Format(results)

    written_data = json.load(open(self.output_file_path))
    self.assertEqual([sample], written_data)

