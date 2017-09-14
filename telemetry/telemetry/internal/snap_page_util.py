# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import util
from telemetry.internal.browser import browser_finder


def SnapPage(finder_options, url, interactive, snapshot_file):
  """ Save the HTML snapshot of the page whose address is |url| to
  |snapshot_file|.
  """
  possible_browser = browser_finder.FindBrowser(finder_options)
  browser = possible_browser.Create(finder_options)
  try:
    tab = browser.tabs[0]
    tab.Navigate(url)
    tab.WaitForDocumentReadyStateToBeComplete()
    if interactive:
      raw_input(
          'Activating interactive mode. Press enter after you finish '
          "interacting with the page to snapshot the page's DOM content.")
    with open(
        os.path.join(util.GetTelemetryThirdPartyDir(), 'snap-it',
                     'HTMLSerializer.js')) as f:
      snapit_script = f.read()
    tab.ExecuteJavaScript(snapit_script)
    tab.ExecuteJavaScript(
        '''
        var serializedDomArray;
        var htmlSerializer = new HTMLSerializer();
        htmlSerializer.processDocument(document);
        htmlSerializer.fillHolesAsync(document, function(s) {
          serializedDomArray = s.html;
        });
        ''')
    print 'Snapshotting content of %s. This could take a while...' % url
    tab.WaitForJavaScriptCondition('serializedDomArray !== undefined')
    serialized_dom = ''.join(tab.EvaluateJavaScript('serializedDomArray'))
    snapshot_file.write(serialized_dom)
  finally:
    browser.Close()
