# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import exceptions


# pylint: disable=R0201
class BaseController(object):
  def StartTracing(self, _):
    raise exceptions.NotImplementedError

  def StopTracing(self):
    raise exceptions.NotImplementedError

  def PullTrace(self):
    raise exceptions.NotImplementedError
