# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds iOS browsers that can be controlled by telemetry."""

import contextlib
import json
import logging
import re
import subprocess
import urllib2

from telemetry.core import platform
from telemetry.core import possible_browser
from telemetry.core import util
from telemetry.core.backends.chrome import inspector_backend


class PossibleIOSBrowser(possible_browser.PossibleBrowser):

  """A running iOS browser instance."""
  def __init__(self, browser_type, finder_options):
    super(PossibleIOSBrowser, self).__init__(browser_type, 'ios',
        finder_options, True)

  # TODO(baxley): Implement the following methods for iOS.
  def Create(self):
    raise NotImplementedError()

  def SupportOptions(self, finder_options):
    raise NotImplementedError()

# Key matches output from ios-webkit-debug-proxy and the value is a readable
# description of the browser.
IOS_BROWSERS = {'CriOS': 'ios-chrome', 'Version': 'ios-safari'}

ALL_BROWSER_TYPES = IOS_BROWSERS.values()

DEVICE_LIST_URL = 'http://127.0.0.1:9221/json'

IOS_WEBKIT_DEBUG_PROXY = 'ios_webkit_debug_proxy'


def SelectDefaultBrowser(_):
  return None  # TODO(baxley): Implement me.


def CanFindAvailableBrowsers():
  return False  # TODO(baxley): Implement me.


def FindAllAvailableBrowsers(finder_options):
  """Find all running iOS browsers on connected devices."""
  ios_device_attached = False
  host = platform.GetHostPlatform()
  if host.GetOSName() == 'mac':
    devices = subprocess.check_output(
        'system_profiler SPUSBDataType', shell=True)
    ios_devices = 'iPod|iPhone|iPad'
    for line in devices.split('\n'):
      if line:
        m = re.match('\s*(%s):' % ios_devices, line)
        if m:
          ios_device_attached = True
          break
  else:
    # TODO(baxley): Add support for all platforms possible. Probably Linux,
    # probably not Windows.
    return []

  if ios_device_attached:
    # TODO(baxley) Use idevice to wake up device or log debug statement.
    if not host.IsApplicationRunning(IOS_WEBKIT_DEBUG_PROXY):
      host.LaunchApplication(IOS_WEBKIT_DEBUG_PROXY)
      if not host.IsApplicationRunning(IOS_WEBKIT_DEBUG_PROXY):
        return []
  else:
    return []

  try:
    # TODO(baxley): Refactor this into a backend file.
    with contextlib.closing(
        urllib2.urlopen(DEVICE_LIST_URL), timeout=10) as device_list:
      json_urls = device_list.read()
    device_urls = json.loads(json_urls)
    if not device_urls:
      logging.debug('No iOS devices found. Will not try searching for iOS '
                    'browsers.')
      return []
  except urllib2.URLError as e:
    logging.error('Error communicating with devices over %s.'
                  % IOS_WEBKIT_DEBUG_PROXY)
    logging.error(str(e))
    return []

  # TODO(baxley): Move to ios-webkit-debug-proxy command class, similar
  # to GetAttachedDevices() in adb_commands.
  data = []
  # Loop through all devices.
  for d in device_urls:
    # Retry a few times since it can take a few seconds for this API to be
    # ready, if ios_webkit_debug_proxy is just launched.
    def GetData():
      try:
        with contextlib.closing(
            urllib2.urlopen('http://%s/json' % d['url']), timeout=10) as f:
          json_result = f.read()
        data = json.loads(json_result)
        return data
      except urllib2.URLError as e:
        logging.error('Error communicating with device over %s.'
                      % IOS_WEBKIT_DEBUG_PROXY)
        logging.error(str(e))
        return False
    try:
      data = util.WaitFor(GetData, 5)
    except util.TimeoutException as e:
      return []

  # Find all running UIWebViews.
  debug_urls = []
  for j in data:
    debug_urls.append(j['webSocketDebuggerUrl'])

  # Get the userAgent for each UIWebView to find the browsers.
  browser_pattern = ('\)\s(%s)\/(\d+[\.\d]*)\sMobile'
                     % '|'.join(IOS_BROWSERS.keys()))
  browsers = []
  for url in debug_urls:
    context = {'webSocketDebuggerUrl':url , 'id':1}
    # TODO(baxley): Replace None with ios_browser_backend, once implemented.
    inspector_alt = inspector_backend.InspectorBackend(None, context)
    res = inspector_alt.EvaluateJavaScript("navigator.userAgent")
    match_browsers = re.search(browser_pattern, res)
    if match_browsers:
      browsers.append(PossibleIOSBrowser(IOS_BROWSERS[match_browsers.group(1)],
                                         finder_options))

  return browsers
