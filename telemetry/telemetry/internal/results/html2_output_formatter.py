# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.internal.results import output_formatter

from tracing import results_renderer


class Html2OutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, metadata, reset_results,
               upload_bucket=None):
    super(Html2OutputFormatter, self).__init__(output_stream)
    self._metadata = metadata
    self._reset_results = reset_results
    self._upload_bucket = upload_bucket

  def Format(self, page_test_results):
    histograms = page_test_results.AsHistogramDicts(self._metadata)
    results_renderer.RenderHTMLView(histograms,
        self._output_stream, self._reset_results)

    if self._upload_bucket:
      file_name = 'html-results/results-' + datetime.datetime.now().strftime(
          '%Y-%m-%d_%H-%M-%S')
      try:
        cloud_storage.Insert(self._upload_bucket, file_name,
                             os.path.abspath(self._output_stream.name))
        print 'View online at',
        print 'http://storage.googleapis.com/{bucket}/{path}'.format(
            bucket=self._upload_bucket, path=file_name)
      except cloud_storage.PermissionError as e:
        logging.error('Cannot upload profiling files to cloud storage due to '
                      ' permission error: %s' % e.message)
