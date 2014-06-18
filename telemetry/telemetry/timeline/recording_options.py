# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class TimelineRecordingOptions(object):
  def __init__(self):
    self.record_timeline = True
    self.record_network = False
