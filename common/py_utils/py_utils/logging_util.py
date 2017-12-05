# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Logging util functions.

It would be named logging, but other modules in this directory use the default
logging module, so that would break them.
"""

import contextlib
import logging

@contextlib.contextmanager
def CaptureLogs(file_stream):
  logger = logging.getLogger()
  fh = logging.StreamHandler(file_stream)
  logger.addHandler(fh)

  try:
    yield
  finally:
    logger = logging.getLogger()
    logger.removeHandler(fh)
