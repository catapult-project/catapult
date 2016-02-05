# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class SystraceAgent(object):
  """The base class for systrace agents.

  A systrace agent contains the command-line options and trace categories to
  capture. Each systrace agent has its own tracing implementation.
  """

  def __init__(self, options, categories):
    """Initialize a systrace agent.

    Args:
      options: The command-line options.
      categories: The trace categories to capture.
    """
    self._options = options
    self._categories = categories

  def start(self):
    """Start tracing.
    """
    raise NotImplementedError()

  def collect_result(self):
    """Collect the result of tracing.

    This function will block while collecting the result. For sync mode, it
    reads the data, e.g., from stdout, until it finishes. For async mode, it
    blocks until the agent is stopped and the data is ready.
    """
    raise NotImplementedError()

  def expect_trace(self):
    """Check if the agent is returning a trace or not.

    This will be determined in collect_result().
    Returns:
      Whether the agent is expecting a trace or not.
    """
    raise NotImplementedError()

  def get_trace_data(self):
    """Get the trace data.

    Returns:
      The trace data.
    """
    raise NotImplementedError()

  def get_class_name(self):
    """Get the class name

    The class name is used to identify the trace type when the trace is written
    to the html file
    Returns:
      The class name.
    """
    raise NotImplementedError()
