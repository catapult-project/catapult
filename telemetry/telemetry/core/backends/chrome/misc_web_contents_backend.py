# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import web_contents
from telemetry.core import util
from telemetry.core.backends.chrome import inspector_backend_list


class MiscWebContentsBackend(inspector_backend_list.InspectorBackendList):
  """A dynamic sequence of web contents not related to tabs and extensions.

  Provides acccess to chrome://oobe/login page.
  """

  def __init__(self, browser_backend):
    super(MiscWebContentsBackend, self).__init__(
        browser_backend, backend_wrapper=web_contents.WebContents)

  @property
  def oobe_exists(self):
    """Lightweight property to determine if the oobe webui is visible. Note that
    the browser goes away when we're logging in, we wait for it to be ready.
    """
    util.WaitFor(self._browser_backend.HasBrowserFinishedLaunching, timeout=30)
    return bool(len(self))

  def GetOobe(self):
    if not len(self):
      return None
    return self[0]

  def ShouldIncludeContext(self, context):
    return context.get('url').startswith('chrome://oobe')
