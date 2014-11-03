# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import app


class AndroidApp(app.App):
  """A running android app instance that can be controlled in a limited way.

  Be sure to clean up after yourself by calling Close() when you are done with
  the app. Or better yet:
    with possible_android_app.Create(options) as android_app:
      ... do all your operations on android_app here
  """
  def __init__(self, backend, platform_backend):
    super(AndroidApp, self).__init__(app_backend=backend,
                                     platform_backend=platform_backend)
  def Close(self):
    raise NotImplementedError()
