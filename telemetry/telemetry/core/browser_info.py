# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

_check_webgl_supported_script = """
(function () {
  var c = document.createElement('canvas');
  var gl = c.getContext('webgl');
  if (gl == null) {
    gl = c.getContext("experimental-webgl");
    if (gl == null) {
      return false;
    }
  }
  return true;
})();
"""

class BrowserInfo(object):
  """A wrapper around browser object that allows looking up infos of the
  browser.
  """
  def __init__(self, browser):
    self._browser = browser

  def HasWebGLSupport(self):
    result = False
    # If no tab is opened, open one and close it after evaluate
    # _check_webgl_supported_script
    if len(self._browser.tabs) == 0 and self._browser.supports_tab_control:
      self._browser.tabs.New()
      tab = self._browser.tabs[0]
      result = tab.EvaluateJavaScript(_check_webgl_supported_script)
      tab.Close()
    elif len(self._browser.tabs) > 0:
      tab = self._browser.tabs[0]
      result = tab.EvaluateJavaScript(_check_webgl_supported_script)
    return result
