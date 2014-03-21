# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""When SIGUSR1 is received, print a stack trace."""

import signal
import traceback


def _PrintDiagnostics(_, stack_frame):
  print """"SIGUSR1 received, printing stack trace:
      %s""" % ("".join(traceback.format_stack(stack_frame)))

def InstallDebuggingHooks():
  # Windows doesn't define SIGUSR1.
  if not hasattr(signal, 'SIGUSR1'):
    return

  signal.signal(signal.SIGUSR1, _PrintDiagnostics)
