# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Finds browsers that can be controlled by telemetry."""

import logging
import operator

from telemetry import decorators
from telemetry.core.backends.chrome import android_browser_finder
from telemetry.core.backends.chrome import cros_browser_finder
from telemetry.core.backends.chrome import desktop_browser_finder
from telemetry.core.backends.chrome import ios_browser_finder
from telemetry.core.backends.webdriver import webdriver_desktop_browser_finder

BROWSER_FINDERS = [
  desktop_browser_finder,
  android_browser_finder,
  cros_browser_finder,
  ios_browser_finder,
  webdriver_desktop_browser_finder,
  ]

ALL_BROWSER_TYPES = reduce(operator.add,
                           [bf.ALL_BROWSER_TYPES for bf in BROWSER_FINDERS])


class BrowserTypeRequiredException(Exception):
  pass


class BrowserFinderException(Exception):
  pass


@decorators.Cache
def FindBrowser(options):
  """Finds the best PossibleBrowser object given a BrowserOptions object.

  Args:
    A BrowserOptions object.

  Returns:
    A PossibleBrowser object.

  Raises:
    BrowserFinderException: Options improperly set, or an error occurred.
  """
  if options.browser_type == 'exact' and options.browser_executable == None:
    raise BrowserFinderException(
        '--browser=exact requires --browser-executable to be set.')
  if options.browser_type != 'exact' and options.browser_executable != None:
    raise BrowserFinderException(
        '--browser-executable requires --browser=exact.')

  if options.browser_type == 'cros-chrome' and options.cros_remote == None:
    raise BrowserFinderException(
        'browser_type=cros-chrome requires cros_remote be set.')
  if (options.browser_type != 'cros-chrome' and
      options.browser_type != 'cros-chrome-guest' and
      options.cros_remote != None):
    raise BrowserFinderException(
        '--remote requires --browser=cros-chrome or cros-chrome-guest.')

  browsers = []
  default_browsers = []
  for finder in BROWSER_FINDERS:
    if (options.browser_type and options.browser_type != 'any' and
        options.browser_type not in finder.ALL_BROWSER_TYPES):
      continue
    curr_browsers = finder.FindAllAvailableBrowsers(options)
    new_default_browser = finder.SelectDefaultBrowser(curr_browsers)
    if new_default_browser:
      default_browsers.append(new_default_browser)
    browsers.extend(curr_browsers)

  if options.browser_type == None:
    if default_browsers:
      default_browser = sorted(default_browsers,
                               key=lambda b: b.last_modification_time())[-1]

      logging.warning('--browser omitted. Using most recent local build: %s' %
                      default_browser.browser_type)
      default_browser.UpdateExecutableIfNeeded()
      return default_browser

    if len(browsers) == 1:
      logging.warning('--browser omitted. Using only available browser: %s' %
                      browsers[0].browser_type)
      browsers[0].UpdateExecutableIfNeeded()
      return browsers[0]

    raise BrowserTypeRequiredException(
        '--browser must be specified. Available browsers:\n%s' %
        '\n'.join(sorted(set([b.browser_type for b in browsers]))))

  if options.browser_type == 'any':
    types = ALL_BROWSER_TYPES
    def CompareBrowsersOnTypePriority(x, y):
      x_idx = types.index(x.browser_type)
      y_idx = types.index(y.browser_type)
      return x_idx - y_idx
    browsers.sort(CompareBrowsersOnTypePriority)
    if len(browsers) >= 1:
      browsers[0].UpdateExecutableIfNeeded()
      return browsers[0]
    else:
      return None

  matching_browsers = [b for b in browsers
      if b.browser_type == options.browser_type and b.SupportsOptions(options)]

  chosen_browser = None
  if len(matching_browsers) == 1:
    chosen_browser = matching_browsers[0]
  elif len(matching_browsers) > 1:
    logging.warning('Multiple browsers of the same type found: %s' % (
                    repr(matching_browsers)))
    chosen_browser = sorted(matching_browsers,
                            key=lambda b: b.last_modification_time())[-1]

  if chosen_browser:
    logging.info('Chose browser: %s' % (repr(chosen_browser)))
    chosen_browser.UpdateExecutableIfNeeded()

  return chosen_browser


@decorators.Cache
def GetAllAvailableBrowserTypes(options):
  """Returns a list of available browser types.

  Args:
    options: A BrowserOptions object.

  Returns:
    A list of browser type strings.

  Raises:
    BrowserFinderException: Options are improperly set, or an error occurred.
  """
  browsers = []
  for finder in BROWSER_FINDERS:
    browsers.extend(finder.FindAllAvailableBrowsers(options))

  type_list = set([browser.browser_type for browser in browsers])
  type_list = list(type_list)
  type_list.sort()
  return type_list
