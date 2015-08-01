# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
class GetTraceHandlesQuery(object):
  @staticmethod
  def FromString(string):
    return GetTraceHandlesQuery()

  def IsMetadataInteresting(self, metadata):
    return True