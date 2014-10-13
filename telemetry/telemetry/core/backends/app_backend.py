# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class AppBackend(object):
  def __init__(self):
    super(AppBackend, self).__init__()
    self._app = None

  def SetApp(self, app):
    self._app = app

  @property
  def app(self):
    return self._app
