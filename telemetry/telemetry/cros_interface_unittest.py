# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(nduca): Rewrite what some of these tests to use mocks instead of
# actually talking to the device. This would improve our coverage quite
# a bit.
import unittest

from telemetry import cros_interface
from telemetry import options_for_unittests
from telemetry import run_tests

class CrOSInterfaceTest(unittest.TestCase):
  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testDeviceSideProcessFailureToLaunch(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)

    def WillFail():
      dsp = cros_interface.DeviceSideProcess(
        cri,
        ['sfsdfskjflwejfweoij'])
      dsp.Close()
    self.assertRaises(OSError, WillFail)

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testDeviceSideProcessCloseDoesClose(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)

    with cros_interface.DeviceSideProcess(
        cri,
        ['sleep', '111']) as dsp:
      procs = cri.ListProcesses()
      sleeps = [x for x in procs
                if x[1] == 'sleep 111']
      assert dsp.IsAlive()
    procs = cri.ListProcesses()
    sleeps = [x for x in procs
              if x[1] == 'sleep 111']
    self.assertEquals(len(sleeps), 0)

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testPushContents(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)
    cri.GetCmdOutput(['rm', '-rf', '/tmp/testPushContents'])
    cri.PushContents('hello world', '/tmp/testPushContents')
    contents = cri.GetFileContents('/tmp/testPushContents')
    self.assertEquals(contents, 'hello world')

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testExists(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)
    self.assertTrue(cri.FileExistsOnDevice('/proc/cpuinfo'))
    self.assertTrue(cri.FileExistsOnDevice('/etc/passwd'))
    self.assertFalse(cri.FileExistsOnDevice('/etc/sdlfsdjflskfjsflj'))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetFileContents(self): # pylint: disable=R0201
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)
    hosts = cri.GetFileContents('/etc/hosts')
    assert hosts.startswith('# /etc/hosts')

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetFileContentsForSomethingThatDoesntExist(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)
    self.assertRaises(
      OSError,
      lambda: cri.GetFileContents('/tmp/209fuslfskjf/dfsfsf'))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testListProcesses(self): # pylint: disable=R0201
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)
    with cros_interface.DeviceSideProcess(
        cri,
        ['sleep', '11']):
      procs = cri.ListProcesses()
      sleeps = [x for x in procs
                if x[1] == 'sleep 11']

      assert len(sleeps) == 1

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testIsServiceRunning(self):
    remote = options_for_unittests.Get().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.Get().cros_ssh_identity)

    self.assertTrue(cri.IsServiceRunning('openssh-server'))

