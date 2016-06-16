# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import signal


@contextlib.contextmanager
def AddSignalHandler(signalnum, additional_handler):
  """Adds a signal handler for the given signal in the wrapped context.

  This runs the new handler after any existing handler rather than
  replacing the existing handler.

  Args:
    signum: The signal for which a handler should be added.
    additional_handler: The handler to add.
  """
  existing_handler = signal.getsignal(signalnum)

  def handler(signum, frame):
    if callable(existing_handler):
      existing_handler(signum, frame)
    additional_handler(signum, frame)

  signal.signal(signalnum, handler)
  yield
  signal.signal(signalnum, existing_handler)

