# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import web_contents


class ExtensionPage(web_contents.WebContents):
  """Represents an extension page in the browser"""
  def __init__(self, extension_id, url, inspector_backend):
    super(ExtensionPage, self).__init__(inspector_backend)
    self.extension_id = extension_id
    self.url = url
    assert url.startswith('chrome-extension://' + extension_id)

  def Reload(self):
    """Reloading an extension page is used as a workaround for an extension
    binding bug for old versions of Chrome (crbug.com/263162). After Navigate
    returns, we are guaranteed that the inspected page is in the correct state.
    """
    self._inspector_backend.Navigate(self.url, None, 10)
