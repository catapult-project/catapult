# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.internal.backends.mandoline import desktop_mandoline_finder
from telemetry.internal.browser import browser_options
from telemetry.internal.platform import desktop_device
from telemetry.testing import system_stub


# This file verifies the logic for finding a mandoline browser instance on all
# platforms at once. It does so by providing stubs for the OS/sys/subprocess
# primitives that the underlying finding logic usually uses to locate a suitable
# browser. We prefer this approach to having to run the same test on every
# platform on which we want this code to work.

class FindTestBase(unittest.TestCase):
  def setUp(self):
    self._finder_options = browser_options.BrowserFinderOptions()
    self._finder_options.chrome_root = '../../../'
    self._finder_stubs = system_stub.Override(desktop_mandoline_finder,
                                              ['os', 'subprocess', 'sys'])
    self._path_stubs = system_stub.Override(desktop_mandoline_finder.path,
                                            ['os', 'sys'])

  def tearDown(self):
    self._finder_stubs.Restore()
    self._path_stubs.Restore()

  @property
  def _files(self):
    return self._path_stubs.os.path.files

  def DoFindAll(self):
    return desktop_mandoline_finder.FindAllAvailableBrowsers(
      self._finder_options, desktop_device.DesktopDevice())

  def DoFindAllTypes(self):
    browsers = self.DoFindAll()
    return [b.browser_type for b in browsers]

  def CanFindAvailableBrowsers(self):
    return desktop_mandoline_finder.CanFindAvailableBrowsers()


class LinuxFindTest(FindTestBase):
  def setUp(self):
    super(LinuxFindTest, self).setUp()

    self._finder_stubs.sys.platform = 'linux2'
    self._path_stubs.sys.platform = 'linux2'
    self._files.append('/foo/mandoline')
    self._files.append('../../../out/Release/mandoline')
    self._files.append('../../../out/Debug/mandoline')

  def testFindAllGivenDefaults(self):
    if not self.CanFindAvailableBrowsers():
      return

    types = self.DoFindAllTypes()
    self.assertEquals(set(types), set(['mandoline-debug', 'mandoline-release']))

  def testFindWithProvidedExecutable(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._finder_options.browser_executable = '/foo/mandoline'
    self.assertIn('exact', self.DoFindAllTypes())

  def testNoErrorWithUnrecognizedExecutableName(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._files.append('/foo/chrome')
    self._finder_options.browser_executable = '/foo/chrome'
    self.assertNotIn('exact', self.DoFindAllTypes())

  def testFindWithProvidedExecutableWhenChromeRootNotSpecified(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._finder_options.chrome_root = None
    self._finder_options.browser_executable = '/foo/mandoline'
    self.assertEquals(['exact'], self.DoFindAllTypes())


class WinFindTest(FindTestBase):
  def setUp(self):
    super(WinFindTest, self).setUp()

    self._finder_stubs.sys.platform = 'win32'
    self._path_stubs.sys.platform = 'win32'
    self._files.append('c:\\tmp\\mandoline.exe')
    self._files.append('..\\..\\..\\out\\Release\\mandoline.exe')
    self._files.append('..\\..\\..\\out\\Debug\\mandoline.exe')

  def testFindAllGivenDefaults(self):
    if not self.CanFindAvailableBrowsers():
      return

    types = self.DoFindAllTypes()
    self.assertEquals(set(types), set(['mandoline-debug', 'mandoline-release']))

  def testFindAllWithExact(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._finder_options.browser_executable = 'c:\\tmp\\mandoline.exe'
    types = self.DoFindAllTypes()
    self.assertEquals(set(types),
                      set(['exact', 'mandoline-debug', 'mandoline-release']))

  def testNoErrorWithUnrecognizedExecutableName(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._files.append('c:\\foo\\chrome.exe')
    self._finder_options.browser_dir = 'c:\\foo\\chrome.exe'
    self.assertNotIn('exact', self.DoFindAllTypes())

  def testFindWithProvidedExecutableWhenChromeRootNotSpecified(self):
    if not self.CanFindAvailableBrowsers():
      return

    self._finder_options.chrome_root = None
    self._finder_options.browser_executable = 'c:\\tmp\\mandoline.exe'
    self.assertEquals(['exact'], self.DoFindAllTypes())
