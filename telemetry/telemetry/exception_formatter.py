# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Print prettier and more detailed exceptions."""

import math
import os
import sys
import traceback

from telemetry.core import util


def InstallUnhandledExceptionFormatter():
  sys.excepthook = PrintFormattedException


def PrintFormattedException(exception_class, exception, tb):
  """Prints an Exception in a more useful format than the default.

  TODO(tonyg): Consider further enhancements. For instance:
    - Report stacks to maintainers like depot_tools does.
    - Add a debug flag to automatically start pdb upon exception.
  """
  def _GetFinalFrame(frame):
    final_frame = None
    while frame is not None:
      final_frame = frame
      frame = frame.tb_next
    return final_frame

  def _AbbreviateMiddle(target, middle, length):
    assert length >= 0, 'Must provide positive length'
    assert len(middle) <= length, 'middle must not be greater than length'
    if len(target) <= length:
      return target
    half_length = (length - len(middle)) / 2.
    return '%s%s%s' % (target[:int(math.floor(half_length))],
                       middle,
                       target[-int(math.ceil(half_length)):])

  base_dir = os.path.abspath(util.GetChromiumSrcDir())
  formatted_exception = traceback.format_exception(
      exception_class, exception, tb)
  extracted_tb = traceback.extract_tb(tb)
  traceback_header = formatted_exception[0].strip()
  exception = ''.join([l[2:] if l[:2] == '  ' else l for l in
                       traceback.format_exception_only(exception_class,
                                                       exception)])
  local_variables = [(variable, value) for variable, value in
                     _GetFinalFrame(tb).tb_frame.f_locals.iteritems()
                     if variable != 'self']

  # Format the traceback.
  print >> sys.stderr
  print >> sys.stderr, traceback_header
  for filename, line, function, text in extracted_tb:
    filename = os.path.abspath(filename)
    if filename.startswith(base_dir):
      filename = filename[len(base_dir)+1:]
    print >> sys.stderr, '  %s at %s:%d' % (function, filename, line)
    print >> sys.stderr, '    %s' % text

  # Format the locals.
  if local_variables:
    print >> sys.stderr
    print >> sys.stderr, 'Locals:'
    longest_variable = max([len(v) for v, _ in local_variables])
    for variable, value in sorted(local_variables):
      value = repr(value)
      possibly_truncated_value = _AbbreviateMiddle(value, ' ... ', 1024)
      truncation_indication = ''
      if len(possibly_truncated_value) != len(value):
        truncation_indication = ' (truncated)'
      print >> sys.stderr, '  %s: %s%s' % (variable.ljust(longest_variable + 1),
                                           possibly_truncated_value,
                                           truncation_indication)

  # Format the exception.
  print >> sys.stderr
  print >> sys.stderr, exception
