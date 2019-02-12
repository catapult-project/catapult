# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class HistogramDeserializer(object):
  def __init__(self, objects):
    self._objects = objects

  def GetObject(self, i):
    return self._objects[i]
