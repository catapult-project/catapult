# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import tempfile
import unittest

from perf_insights import corpus_driver_cmdline
from perf_insights import corpus_query
from perf_insights_build import pi_report_to_html
import perf_insights_project


class TestArgs(object):
  def __init__(self, trace_directory):
    self.corpus = 'local-directory'
    self.trace_directory = trace_directory


class PiReportToHTMLTests(unittest.TestCase):

  def test_basic(self):
    # Note: We can't use "with" when working with tempfile.NamedTemporaryFile as
    # that does not work on Windows. We use the longer, more clunky version
    # instead. See https://bugs.python.org/issue14243 for detials.
    raw_tmpfile = tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', delete=False)
    raw_tmpfile.close()
    try:
      project = perf_insights_project.PerfInsightsProject()
      with codecs.open(raw_tmpfile.name, 'w', encoding='utf-8') as tmpfile:
        corpus_driver = corpus_driver_cmdline.GetCorpusDriver(
            None, TestArgs(project.perf_insights_test_data_path))
        res = pi_report_to_html.PiReportToHTML(
            tmpfile, corpus_driver,
            project.GetAbsPathFromHRef(
                '/perf_insights/ui/reports/startup_report.html'),
            corpus_query.CorpusQuery.FromString('MAX_TRACE_HANDLES=2'),
            quiet=True)
        self.assertEquals(res, 0)
    finally:
      os.remove(raw_tmpfile.name)
