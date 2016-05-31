# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging
import os

from catapult_base import cloud_storage

from telemetry.internal.results import output_formatter

import tracing_project

from py_vulcanize import generate


class Html2OutputFormatter(output_formatter.OutputFormatter):
  def __init__(self, output_stream, reset_results, upload_results):
    super(Html2OutputFormatter, self).__init__(output_stream)
    self._upload_results = upload_results

    # Format() needs to append to output_stream, which is easiest to do by
    # re-opening in 'a' mode, which requires the filename instead of the file
    # object handle, and closing the file so that it can be re-opened in
    # Format().
    self._output_filename = output_stream.name

    # If the results should be reset or is empty, then write the prefix.
    stat = os.stat(self._output_filename)
    if reset_results or stat.st_size == 0:
      output_stream.write(self._GetHtmlPrefix())
    output_stream.close()

  def _GetHtmlPrefix(self):
    project = tracing_project.TracingProject()
    vulcanizer = project.CreateVulcanizer()
    modules = ['tracing.results2_template']
    load_sequence = vulcanizer.CalcLoadSequenceForModuleNames(modules)
    return generate.GenerateStandaloneHTMLAsString(load_sequence)

  def Format(self, page_test_results):
    with file(self._output_filename, 'a') as f:
      f.write('\n'.join([
          '',
          '<script>',
          'values.addValuesFromDicts(%s);' % json.dumps(
              page_test_results.value_set),
          '</script>',
          '']))

    if self._upload_results:
      file_path = os.path.abspath(self._output_stream.name)
      file_name = 'html-results/results-%s' % datetime.datetime.now().strftime(
          '%Y-%m-%d_%H-%M-%S')
      try:
        cloud_storage.Insert(cloud_storage.PUBLIC_BUCKET, file_name, file_path)
        print
        print ('View online at '
               'http://storage.googleapis.com/chromium-telemetry/%s'
               % file_name)
      except cloud_storage.PermissionError as e:
        logging.error('Cannot upload profiling files to cloud storage due to '
                      ' permission error: %s' % e.message)
    print
    print 'View result at file://%s' % os.path.abspath(
        self._output_stream.name)
