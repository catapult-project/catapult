#!/usr/bin/env python

# Copyright (c) 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Decorator that adds timeout functionality to a function.

from devil.utils import timeout_retry
from devil.utils import reraiser_thread
import functools

def Timeout(default_timeout):
  return lambda func: timeout_deco(func, default_timeout)

# Note: Even though the "timeout" keyword argument is the only
# keyword argument that will need to be given to the decorated function,
# we still have to use the **kwargs syntax, because we have to use
# the *args syntax here before (since the decorator decorates functions
# with different numbers of positional arguments) and Python doesn't allow
# a single named keyword argument after *args.
# (e.g., 'def foo(*args, bar=42):' is a syntax error)

def timeout_deco(func, default_timeout):
  @functools.wraps(func)
  def run_with_timeout(*args, **kwargs):
    if 'timeout' in kwargs:
      timeout = kwargs['timeout']
    else:
      timeout = default_timeout
    try:
      return timeout_retry.Run(func, timeout, 0, args=args)
    except reraiser_thread.TimeoutError:
      print '%s timed out.' % func.__name__
      return False
  return run_with_timeout
