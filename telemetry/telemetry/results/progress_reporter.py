# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class ProgressReporter(object):
  """A class that reports progress of a benchmark to the output stream.

  The reporter produces output whenever a significant event happens
  during the progress of a benchmark, including (but not limited to):
  when a page run is started, when a page run finished, any failures
  during a page run.

  The default implementation outputs nothing.
  """

  def __init__(self, output_stream):
    self.output_stream = output_stream

  def WillRunPage(self, page):
    pass

  def DidAddValue(self, value):
    pass

  def DidAddSuccess(self, page):
    pass

  def DidFinishAllTests(self, page_test_results):
    pass
