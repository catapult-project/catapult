# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.



class PossibleBrowser(object):
  """A browser that can be controlled.

  Call Create() to launch the browser and begin manipulating it..
  """

  def __init__(self, browser_type, target_os, finder_options,
               supports_tab_control):
    self._browser_type = browser_type
    self._target_os = target_os
    self._finder_options = finder_options
    self._supports_tab_control = supports_tab_control
    self._platform = None
    self._platform_backend = None
    self._archive_path = None
    self._append_to_existing_wpr = False
    self._make_javascript_deterministic = True
    self._credentials_path = None

  def __repr__(self):
    return 'PossibleBrowser(browser_type=%s)' % self.browser_type

  @property
  def browser_type(self):
    return self._browser_type

  @property
  def target_os(self):
    """Target OS, the browser will run on."""
    return self._target_os

  @property
  def finder_options(self):
    return self._finder_options

  @property
  def supports_tab_control(self):
    return self._supports_tab_control

  @property
  def platform(self):
    self._InitPlatformIfNeeded()
    return self._platform

  def _InitPlatformIfNeeded(self):
    raise NotImplementedError()

  def Create(self):
    raise NotImplementedError()

  def SupportsOptions(self, finder_options):
    """Tests for extension support."""
    raise NotImplementedError()

  def IsRemote(self):
    return False

  def RunRemote(self):
    pass

  def UpdateExecutableIfNeeded(self):
    pass

  def last_modification_time(self):
    return -1

  def SetReplayArchivePath(self, archive_path, append_to_existing_wpr,
                           make_javascript_deterministic):
    self._archive_path = archive_path
    self._append_to_existing_wpr = append_to_existing_wpr
    self._make_javascript_deterministic = make_javascript_deterministic

  def SetCredentialsPath(self, credentials_path):
    self._credentials_path = credentials_path
