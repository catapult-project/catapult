# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class MapResults(object):
  def __init__(self, output_file):
    pass

  @property
  def had_failures(self):
    raise NotImplemented()

  def WillMapTraces(self):
    raise NotImplemented()

  def WillMapSingleTrace(self, trace_handle):
    raise NotImplemented()

  def DidMapSingleTrace(self, trace_handle, value):
    raise NotImplemented()

  def DidMapTraces(self):
    raise NotImplemented()

