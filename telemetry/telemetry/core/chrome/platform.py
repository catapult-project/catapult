# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class Platform(object):
  """The platform that the target browser is running on.

  Provides a limited interface to obtain stats from the platform itself, where
  possible.
  """

  def GetSurfaceCollector(self, trace_tag):
    """Platforms may be able to collect GL surface stats."""
    class StubSurfaceCollector(object):
      def __init__(self, trace_tag):
        pass
      def __enter__(self):
        pass
      def __exit__(self, *args):
        pass

    return StubSurfaceCollector(trace_tag)
