# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time


class WallTimeLogger(object):
  def __init__(self, label):
    self._label = label
    self._start = None
    self.seconds = 0

  def _Now(self):
    return time.time()

  def _Suffix(self):
    return 'wall'

  def __enter__(self):
    self._start = self._Now()

  def __exit__(self, *unused_args):
    self.seconds = self._Now() - self._start
    logging.info('%s:%s=%f', self._label, self._Suffix(), self.seconds)


class CpuTimeLogger(WallTimeLogger):
  def _Now(self):
    return time.clock()

  def _Suffix(self):
    return 'cpu'


def TimeWall(label):
  def Decorator(wrapped):
    def Wrapper(*a, **kw):
      with WallTimeLogger(label):
        return wrapped(*a, **kw)
    return Wrapper
  return Decorator


def TimeCpu(label):
  def Decorator(wrapped):
    def Wrapper(*a, **kw):
      with CpuTimeLogger(label):
        return wrapped(*a, **kw)
    return Wrapper
  return Decorator
