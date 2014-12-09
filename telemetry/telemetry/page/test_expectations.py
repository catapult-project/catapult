# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch

OS_MODIFIERS = ['win', 'xp', 'vista', 'win7',
                'mac', 'leopard', 'snowleopard', 'lion', 'mountainlion',
                'mavericks', 'yosemite', 'linux', 'chromeos', 'android']
GPU_MODIFIERS = ['amd', 'arm', 'broadcom', 'hisilicon', 'intel', 'imagination',
                 'nvidia', 'qualcomm', 'vivante']
CONFIG_MODIFIERS = ['debug', 'release']

class _Expectation(object):
  def __init__(self, expectation, parent_expectations,
      pattern, conditions=None, bug=None):
    self.expectation = expectation.lower()
    self.name_pattern = pattern
    self.url_pattern = pattern
    self.bug = bug

    self.os_conditions = []
    self.gpu_conditions = []
    self.config_conditions = []
    self.device_id_conditions = []
    # These are made legal by TestExpectations.IsValidUserDefinedCondition.
    self.user_defined_conditions = []

    # Make sure that non-absolute paths are searchable
    if not '://' in self.url_pattern:
      self.url_pattern = '*/' + self.url_pattern

    if conditions:
      for c in conditions:
        if isinstance(c, tuple):
          c0 = c[0].lower()
          if c0 in GPU_MODIFIERS:
            self.device_id_conditions.append((c0, c[1]))
          elif parent_expectations.IsValidUserDefinedCondition(c0):
            self.user_defined_conditions.append((c0, c[1]))
          else:
            raise ValueError('Unknown expectation condition: "%s"' % c0)
        else:
          condition = c.lower()
          if condition in OS_MODIFIERS:
            self.os_conditions.append(condition)
          elif condition in GPU_MODIFIERS:
            self.gpu_conditions.append(condition)
          elif condition in CONFIG_MODIFIERS:
            self.config_conditions.append(condition)
          elif parent_expectations.IsValidUserDefinedCondition(condition):
            self.user_defined_conditions.append(condition)
          else:
            raise ValueError('Unknown expectation condition: "%s"' % condition)

class TestExpectations(object):
  """A class which defines the expectations for a page set test execution"""

  def __init__(self):
    self.expectations = []
    self.SetExpectations()

  def SetExpectations(self):
    """Called on creation. Override to set up custom expectations."""
    pass

  def Fail(self, url_pattern, conditions=None, bug=None):
    self._Expect('fail', url_pattern, conditions, bug)

  def Skip(self, url_pattern, conditions=None, bug=None):
    self._Expect('skip', url_pattern, conditions, bug)

  def _Expect(self, expectation, url_pattern, conditions=None, bug=None):
    self.expectations.append(_Expectation(expectation, self, url_pattern,
      conditions, bug))

  def GetExpectationForPage(self, browser, page):
    platform = browser.platform
    gpu_info = None

    for e in self.expectations:
      matches_url = fnmatch.fnmatch(page.url, e.url_pattern)
      matches_name = page.name and fnmatch.fnmatch(page.name, e.name_pattern)
      if matches_url or matches_name:
        if gpu_info == None and browser.supports_system_info:
          gpu_info = browser.GetSystemInfo().gpu
        if self.ModifiersApply(platform, gpu_info, e):
          return e.expectation
    return 'pass'

  def _GetGpuVendorString(self, gpu_info):
    if gpu_info:
      primary_gpu = gpu_info.devices[0]
      if primary_gpu:
        vendor_string = primary_gpu.vendor_string.lower()
        vendor_id = primary_gpu.vendor_id
        if vendor_string:
          return vendor_string.split(' ')[0]
        elif vendor_id == 0x10DE:
          return 'nvidia'
        elif vendor_id == 0x1002:
          return 'amd'
        elif vendor_id == 0x8086:
          return 'intel'

    return 'unknown_gpu'

  def _GetGpuDeviceId(self, gpu_info):
    if gpu_info:
      primary_gpu = gpu_info.devices[0]
      if primary_gpu:
        return primary_gpu.device_id or primary_gpu.device_string

    return 0

  def ModifiersApply(self, platform, gpu_info, expectation):
    """Determines if the conditions for an expectation apply to this system.
    Can be overridden by subclasses to support new user-defined conditions.

    Args:
      platform: an instance of telemetry.core.platform.Platform which
          is the platform the browser instance is running on during
          the page test.
      gpu_info: an instance of telemetry.core.GPUInfo which describes
          the GPU configuration of the machine on which the browser is
          running.
      expectation: a object which is guaranteed to have the property
          "user_defined_conditions" defined, which is an array of
          strings or tuples specified in the test expectations for
          which IsValidUserDefinedCondition returned true.
    """
    os_matches = (not expectation.os_conditions or
        platform.GetOSName() in expectation.os_conditions or
        platform.GetOSVersionName() in expectation.os_conditions)

    gpu_vendor = self._GetGpuVendorString(gpu_info)
    gpu_device_id = self._GetGpuDeviceId(gpu_info)

    gpu_matches = ((not expectation.gpu_conditions and
        not expectation.device_id_conditions) or
        gpu_vendor in expectation.gpu_conditions or
        (gpu_vendor, gpu_device_id) in expectation.device_id_conditions)

    return os_matches and gpu_matches

  def IsValidUserDefinedCondition(self, _condition):
    """Returns true if the given condition should be treated as a
    valid user-defined condition.

    Args:
      _condition: a string. Returning true causes a new entry to be
          added to the user_defined_expectations for the expectation
          currently being parsed. The entry added may be either the
          simple string of the condition, or a tuple if the condition
          represents the name of a new GPU type and there was an
          associated device ID in the expectation.
    """
    return False
