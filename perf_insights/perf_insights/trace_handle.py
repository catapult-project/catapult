# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import uuid

class TraceHandle(object):
  def __init__(self, run_info):
    self.run_info = run_info

  def Open(self):
    # Returns a with-able object containing a name.
    raise NotImplementedError()

