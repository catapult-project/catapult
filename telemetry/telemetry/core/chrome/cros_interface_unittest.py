# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(nduca): Rewrite what some of these tests to use mocks instead of
# actually talking to the device. This would improve our coverage quite
# a bit.
import unittest
import socket
import sys

from telemetry.core import util
from telemetry.core.chrome import cros_browser_backend
from telemetry.core.chrome import cros_interface
from telemetry.test import options_for_unittests
from telemetry.test import run_tests

class CrOSInterfaceTest(unittest.TestCase):
  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testPushContents(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)
    cri.RunCmdOnDevice(['rm', '-rf', '/tmp/testPushContents'])
    cri.PushContents('hello world', '/tmp/testPushContents')
    contents = cri.GetFileContents('/tmp/testPushContents')
    self.assertEquals(contents, 'hello world')

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testExists(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)
    self.assertTrue(cri.FileExistsOnDevice('/proc/cpuinfo'))
    self.assertTrue(cri.FileExistsOnDevice('/etc/passwd'))
    self.assertFalse(cri.FileExistsOnDevice('/etc/sdlfsdjflskfjsflj'))

  def testExistsLocal(self):
    if not sys.platform.startswith('linux'):
      return

    cri = cros_interface.CrOSInterface()
    self.assertTrue(cri.FileExistsOnDevice('/proc/cpuinfo'))
    self.assertTrue(cri.FileExistsOnDevice('/etc/passwd'))
    self.assertFalse(cri.FileExistsOnDevice('/etc/sdlfsdjflskfjsflj'))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetFileContents(self): # pylint: disable=R0201
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)
    hosts = cri.GetFileContents('/etc/hosts')
    assert hosts.startswith('# /etc/hosts')

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetFileContentsForSomethingThatDoesntExist(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)
    self.assertRaises(
      OSError,
      lambda: cri.GetFileContents('/tmp/209fuslfskjf/dfsfsf'))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testIsServiceRunning(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)

    self.assertTrue(cri.IsServiceRunning('openssh-server'))

  def testIsServiceRunningLocal(self):
    if not sys.platform.startswith('linux'):
      return
    cri = cros_interface.CrOSInterface()
    self.assertTrue(cri.IsServiceRunning('dbus'))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetRemotePortAndIsHTTPServerRunningOnPort(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)

    # Create local server.
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.listen(0)

    # Get remote port and ensure that it was unused.
    remote_port = cri.GetRemotePort()
    self.assertFalse(cri.IsHTTPServerRunningOnPort(remote_port))

    # Forward local server's port to remote device's remote_port.
    forwarder = cros_browser_backend.SSHForwarder(
        cri, 'R', util.PortPair(port, remote_port))

    # At this point, remote device should be able to connect to local server.
    self.assertTrue(cri.IsHTTPServerRunningOnPort(remote_port))

    # Next remote port shouldn't be the same as remote_port, since remote_port
    # is now in use.
    self.assertTrue(cri.GetRemotePort() != remote_port)

    # Close forwarder and local server ports.
    forwarder.Close()
    sock.close()

    # Device should no longer be able to connect to remote_port since it is no
    # longer in use.
    self.assertFalse(cri.IsHTTPServerRunningOnPort(remote_port))

  @run_tests.RequiresBrowserOfType('cros-chrome')
  def testGetRemotePortReservedPorts(self):
    remote = options_for_unittests.GetCopy().cros_remote
    cri = cros_interface.CrOSInterface(
      remote,
      options_for_unittests.GetCopy().cros_ssh_identity)

    # Should return 2 separate ports even though the first one isn't technically
    # being used yet.
    remote_port_1 = cri.GetRemotePort()
    remote_port_2 = cri.GetRemotePort()

    self.assertTrue(remote_port_1 != remote_port_2)
