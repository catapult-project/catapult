# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util

def NavigateToTestFile(tab, filename, script_to_evaluate_on_commit=None):
  """Navigates |tab| to |filename| in the unittest data directory.

  Also sets up http server to point to the unittest data directory.
  """
  tab.browser.SetHTTPServerDirectories(util.GetUnittestDataDir())
  path = os.path.join(util.GetUnittestDataDir(), filename)
  tab.Navigate(tab.browser.http_server.UrlOf(path),
               script_to_evaluate_on_commit)
  tab.WaitForDocumentReadyStateToBeComplete()
  return path

