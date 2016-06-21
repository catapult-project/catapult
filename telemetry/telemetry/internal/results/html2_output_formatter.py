# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import os
import re

from catapult_base import cloud_storage

from telemetry.internal.results import output_formatter

import tracing_project

from py_vulcanize import generate


class Html2OutputFormatter(output_formatter.OutputFormatter):
  _JSON_TAG = '<div id="value-set-json">%s</div>'

  def __init__(self, output_stream, reset_results, upload_results):
    super(Html2OutputFormatter, self).__init__(output_stream)
    self._upload_results = upload_results
    self._values = [] if reset_results else self._ReadExistingResults()

  @property
  def values(self):
    return self._values

  def _ReadExistingResults(self):
    results_html = self._output_stream.read()
    if not results_html:
      return []
    m = re.search(self._JSON_TAG % '(.*?)', results_html,
                  re.MULTILINE | re.DOTALL)
    if not m:
      logging.warn('Failed to extract previous results from HTML output')
      return []
    return json.loads(m.group(1))

  def Format(self, page_test_results):
    self._values.extend(page_test_results.value_set)
    vulcanizer = tracing_project.TracingProject().CreateVulcanizer()
    load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(
        ['tracing.results2_template'])
    html = generate.GenerateStandaloneHTMLAsString(load_sequence)
    html = html.replace(self._JSON_TAG % '', self._JSON_TAG % json.dumps(
        self._values, separators=(',', ':')))
    self._output_stream.seek(0)
    self._output_stream.write(html)
    self._output_stream.truncate()

    file_path = os.path.abspath(self._output_stream.name)
    if self._upload_results:
      remote_path = ('html-results/results-%s' %
                     datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
      try:
        cloud_storage.Insert(
            cloud_storage.PUBLIC_BUCKET, remote_path, file_path)
        print 'View online at',
        print 'http://storage.googleapis.com/chromium-telemetry/' + remote_path
      except cloud_storage.PermissionError as e:
        logging.error('Cannot upload profiling files to cloud storage due ' +
                      'to permission error: ' + e.message)
    print 'View result at file://' + file_path
