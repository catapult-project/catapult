# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A library for cross-platform browser tests."""

import inspect
import logging
import os
import sys


# Ensure Python >= 2.6
if sys.version_info < (2, 6):
  logging.critical('Need Python 2.6 or greater.')
  sys.exit(1)


from telemetry import exception_formatter
exception_formatter.InstallUnhandledExceptionFormatter()

from telemetry.core.browser import Browser
from telemetry.core.browser_options import BrowserFinderOptions
from telemetry.core.tab import Tab

from telemetry.page.page_measurement import PageMeasurement
from telemetry.page.page_runner import Run as RunPage


__all__ = []

# Find all local vars that are classes or functions and make sure they're in the
# __all__ array so they're included in docs.
for x in dir():
  if x.startswith('_'):
    continue
  if x in (inspect, os, sys):
    continue
  m = sys.modules[__name__]
  if (inspect.isclass(getattr(m, x)) or
      inspect.isfunction(getattr(m, x))):
    __all__.append(x)


def RemoveAllStalePycFiles(base_dir):
  for dirname, _, filenames in os.walk(base_dir):
    if '.svn' in dirname or '.git' in dirname:
      continue
    for filename in filenames:
      root, ext = os.path.splitext(filename)
      if ext != '.pyc':
        continue

      pyc_path = os.path.join(dirname, filename)
      py_path = os.path.join(dirname, root + '.py')
      if os.path.exists(py_path):
        continue

      try:
        os.remove(pyc_path)
      except OSError:
        # Avoid race, in case we're running simultaneous instances.
        pass

    if os.listdir(dirname):
      continue

    try:
      os.removedirs(dirname)
    except OSError:
      # Avoid race, in case we're running simultaneous instances.
      pass


RemoveAllStalePycFiles(os.path.dirname(__file__))
