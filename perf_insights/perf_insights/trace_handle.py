# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class TraceHandle(object):

  def __init__(self, canonical_url):
    self.canonical_url = canonical_url

  def Open(self):
    # Returns a with-able object containing a name.
    raise NotImplementedError()

