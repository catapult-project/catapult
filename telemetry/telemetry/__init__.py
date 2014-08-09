# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A library for cross-platform browser tests."""

import inspect
import logging
import os
import sys

# Ensure Python >= 2.7.
if sys.version_info < (2, 7):
  print >> sys.stderr, 'Need Python 2.7 or greater.'
  sys.exit(-1)

from telemetry.util import global_hooks
global_hooks.InstallHooks()

from telemetry.core.browser import Browser
from telemetry.core.browser_options import BrowserFinderOptions
from telemetry.core.tab import Tab

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
