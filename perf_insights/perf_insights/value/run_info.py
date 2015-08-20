# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import uuid


# This value must stay sync'd with the constant of the same name
# in run_info.py.
PI_VALUE_RUN_INFO_ID = 'perf_insights.value.RunInfo'


class RunInfo(object):
  def __init__(self, url, display_name=None, run_id=None, metadata=None):
    if run_id is not None:
      self.run_id = run_id
    else:
      self.run_id = str(uuid.uuid4())

    self.url = url
    self.display_name = display_name or url
    self.metadata = metadata or {}

  def AsDict(self):
    d = {
      'run_id': self.run_id,
      'type': PI_VALUE_RUN_INFO_ID,
      'url': self.url,
      'metadata': self.metadata
    }
    if self.display_name != self.url:
      d['display_name'] = self.display_name

    return d

  @staticmethod
  def FromDict(d):
    if d['type'] != PI_VALUE_RUN_INFO_ID:
      raise Exception('Unsupported run_info format')
    return RunInfo(d['url'],
                   d['display_name'],
                   run_id=d['run_id'],
                   metadata=d.get('metadata', None))

