# Copyright (c) 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import codecs
import os
import json
import sys

from telemetry.core import util
from telemetry.internal.browser import browser_finder
from telemetry.internal.browser import browser_options


HTML_SUFFIX = '.html'


def _TransmitLargeJSONToTab(tab, json_obj, js_holder_name):
  tab.ExecuteJavaScript(
      'var {{ @js_holder_name }} = "";', js_holder_name=js_holder_name)

  # To avoid crashing devtool connection (details in crbug.com/763119#c16),
  # we break down the json string to chunks which each chunk has a maximum
  # size of 100000 characters (100000 seems to not break the connection and
  # makes sending data reasonably fast).
  k = 0
  step_size = 100000
  json_obj_string = json.dumps(json_obj)
  while k < len(json_obj_string):
    sub_string_chunk = json_obj_string[k: k + step_size]
    k += step_size
    tab.ExecuteJavaScript(
        '{{ @js_holder_name }} += {{ sub_string_chunk }};',
        js_holder_name=js_holder_name, sub_string_chunk=sub_string_chunk)

  tab.ExecuteJavaScript(
      '{{ @js_holder_name }} = JSON.parse({{ @js_holder_name }});',
      js_holder_name=js_holder_name)


def _CreateBrowser(finder_options, enable_browser_log):
  if enable_browser_log:
    # Enable NON_VERBOSE_LOGGING which also contains devtool's console logs.
    finder_options.browser_options.logging_verbosity = (
        browser_options.BrowserOptions.NON_VERBOSE_LOGGING)
    # Do not upload the log to cloud storage.
    finder_options.browser_options.logs_cloud_bucket = None

  possible_browser = browser_finder.FindBrowser(finder_options)
  return possible_browser.Create(finder_options)


def _ReadSnapItSource(path):
  """ Returns the contents of the snap-it source file at the given path
  relative to the snap-it repository.
  """
  full_path = os.path.join(util.GetCatapultThirdPartyDir(), 'snap-it', path)
  with open(full_path) as f:
    return f.read()


def _SnapPageToFile(finder_options, url, interactive,
                    snapshot_file, enable_browser_log):
  """ Save the HTML snapshot of the page whose address is |url| to
  |snapshot_file|.
  """
  browser = _CreateBrowser(finder_options, enable_browser_log)
  try:
    tab = browser.tabs[0]
    tab.Navigate(url)
    if interactive:
      raw_input(
          'Activating interactive mode. Press enter after you finish '
          "interacting with the page to snapshot the page's DOM content.")

    sys.stdout.write(
        'Snapshotting content of %s. This could take a while...\n' % url)
    tab.WaitForDocumentReadyStateToBeComplete()
    tab.action_runner.WaitForNetworkQuiescence()

    snapit_script = _ReadSnapItSource('HTMLSerializer.js')
    dom_combining_script = _ReadSnapItSource('popup.js')
    serialized_doms = []

    # Serialize the dom in each frame.
    for context_id in tab.EnableAllContexts():
      tab.ExecuteJavaScript(snapit_script, context_id=context_id)
      tab.ExecuteJavaScript(
          '''
          var serializedDom;
          var htmlSerializer = new HTMLSerializer();
          htmlSerializer.processDocument(document);
          htmlSerializer.fillHolesAsync(document, function(s) {
            serializedDom = s.asDict();
          });
          ''', context_id=context_id)
      tab.WaitForJavaScriptCondition(
          'serializedDom !== undefined', context_id=context_id)
      serialized_doms.append(tab.EvaluateJavaScript(
          'serializedDom', context_id=context_id))

    # Execute doms combining code in blank page to minimize the chance of V8
    # OOM.
    tab.Navigate('about:blank')
    tab.WaitForDocumentReadyStateToBeComplete()

    # Sending all the serialized doms back to tab execution context.
    tab.ExecuteJavaScript('var serializedDoms = [];')
    for i in xrange(len(serialized_doms)):
      sys.stdout.write('Processing dom of frame #%i / %i\r' %
                       (i, len(serialized_doms)))
      sys.stdout.flush()
      _TransmitLargeJSONToTab(tab, serialized_doms[i], 'sub_dom')
      tab.ExecuteJavaScript('serializedDoms.push(sub_dom);')

    # Combine all the doms to one HTML string.
    tab.EvaluateJavaScript(dom_combining_script)
    page_snapshot = tab.EvaluateJavaScript('outputHTMLString(serializedDoms);')

    snapshot_file.write(page_snapshot)
  finally:
    browser.Close()


def SnapPage(finder_options, url, interactive, snapshot_path,
             enable_browser_log):
  """ Save the HTML snapshot of the page whose address is |url| to
  the file located at the relative path |snapshot_path|.
  """
  if not snapshot_path.endswith(HTML_SUFFIX):
    raise ValueError('Snapshot path should end with \'%s\' [value=\'%s\'].' % (
        HTML_SUFFIX, snapshot_path))

  snapshot_path = os.path.abspath(snapshot_path)
  with codecs.open(snapshot_path, 'w', 'utf-8') as f:
    _SnapPageToFile(finder_options, url, interactive, f, enable_browser_log)
  print 'Successfully saved snapshot to file://%s' % snapshot_path
