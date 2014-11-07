# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class AppBackend(object):
  def __init__(self, app_type):
    super(AppBackend, self).__init__()
    self._app = None
    self._app_type = app_type

  def __del__(self):
    self.Close()

  def SetApp(self, app):
    self._app = app

  @property
  def app(self):
    return self._app

  @property
  def app_type(self):
    return self._app_type

  def Start(self):
    NotImplementedError()

  def Close(self):
    NotImplementedError()

  @property
  def pid(self):
    NotImplementedError()

  def IsAppRunning(self):
    NotImplementedError()

  def GetStandardOutput(self):
    NotImplementedError()

  def GetStackTrace(self):
    NotImplementedError()
