# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os

from py_utils import cloud_storage

from telemetry.internal.results import output_formatter

from tracing import results_renderer


class Html2OutputFormatter(output_formatter.OutputFormatter):
  _JSON_TAG = '<div id="value-set-json">%s</div>'

  def __init__(self, output_stream, reset_results, upload_results):
    super(Html2OutputFormatter, self).__init__(output_stream)
    self._upload_results = upload_results
    self._reset_results = reset_results

  def Format(self, page_test_results):
    results_renderer.RenderHTMLView(page_test_results.value_set,
                                    self._output_stream, self._reset_results)
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
