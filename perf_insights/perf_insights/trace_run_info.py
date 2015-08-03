# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import uuid


class TraceRunInfo(object):
  def __init__(self, url, display_name=None, run_id=None):
    if run_id is not None:
      self.run_id = run_id
    else:
      self.run_id = str(uuid.uuid4())

    self.url = url
    self.display_name = display_name or url

  def AsDict(self):
    return {
      "run_id": self.run_id,
      "type": "mapped_trace",
      "url": self.url
    }


  @staticmethod
  def FromDict(d):
    return TraceRunInfo(d["url"],
                        d["display_name"],
                        run_id=d["run_id"])

