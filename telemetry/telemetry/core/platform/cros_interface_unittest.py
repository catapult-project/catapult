# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(nduca): Rewrite what some of these tests to use mocks instead of
# actually talking to the device. This would improve our coverage quite
# a bit.

import socket
import tempfile
import unittest

from telemetry.core import forwarders
from telemetry.core.forwarders import cros_forwarder
from telemetry.core.platform import cros_interface
from telemetry import decorators
from telemetry.unittest_util import options_for_unittests


class CrOSInterfaceTest(unittest.TestCase):
  def _GetCRI(self):
    remote = options_for_unittests.GetCopy().cros_remote
    remote_ssh_port = options_for_unittests.GetCopy().cros_remote_ssh_port
    return cros_interface.CrOSInterface(
        remote, remote_ssh_port,
        options_for_unittests.GetCopy().cros_ssh_identity)

  @decorators.Enabled('cros-chrome')
  def testPushContents(self):
    with self._GetCRI() as cri:
      cri.RunCmdOnDevice(['rm', '-rf', '/tmp/testPushContents'])
      cri.PushContents('hello world', '/tmp/testPushContents')
      contents = cri.GetFileContents('/tmp/testPushContents')
      self.assertEquals(contents, 'hello world')

  @decorators.Enabled('cros-chrome')
  def testExists(self):
    with self._GetCRI() as cri:
      self.assertTrue(cri.FileExistsOnDevice('/proc/cpuinfo'))
      self.assertTrue(cri.FileExistsOnDevice('/etc/passwd'))
      self.assertFalse(cri.FileExistsOnDevice('/etc/sdlfsdjflskfjsflj'))

  @decorators.Enabled('linux')
  def testExistsLocal(self):
    with cros_interface.CrOSInterface() as cri:
      self.assertTrue(cri.FileExistsOnDevice('/proc/cpuinfo'))
      self.assertTrue(cri.FileExistsOnDevice('/etc/passwd'))
      self.assertFalse(cri.FileExistsOnDevice('/etc/sdlfsdjflskfjsflj'))

  @decorators.Enabled('cros-chrome')
  def testGetFileContents(self): # pylint: disable=R0201
    with self._GetCRI() as cri:
      hosts = cri.GetFileContents('/etc/lsb-release')
      self.assertTrue('CHROMEOS' in hosts)

  @decorators.Enabled('cros-chrome')
  def testGetFileContentsNonExistent(self):
    with self._GetCRI() as cri:
      f = tempfile.NamedTemporaryFile()
      cri.PushContents('testGetFileNonExistent', f.name)
      cri.RmRF(f.name)
      self.assertRaises(
          OSError,
          lambda: cri.GetFileContents(f.name))

  @decorators.Enabled('cros-chrome')
  def testGetFile(self): # pylint: disable=R0201
    with self._GetCRI() as cri:
      f = tempfile.NamedTemporaryFile()
      cri.GetFile('/etc/lsb-release', f.name)
      with open(f.name, 'r') as f2:
        res = f2.read()
        self.assertTrue('CHROMEOS' in res)

  @decorators.Enabled('cros-chrome')
  def testGetFileNonExistent(self):
    with self._GetCRI() as cri:
      f = tempfile.NamedTemporaryFile()
      cri.PushContents('testGetFileNonExistent', f.name)
      cri.RmRF(f.name)
      self.assertRaises(
          OSError,
          lambda: cri.GetFile(f.name))

  @decorators.Enabled('cros-chrome')
  def testIsServiceRunning(self):
    with self._GetCRI() as cri:
      self.assertTrue(cri.IsServiceRunning('openssh-server'))

  @decorators.Enabled('linux')
  def testIsServiceRunningLocal(self):
    with cros_interface.CrOSInterface() as cri:
      self.assertTrue(cri.IsServiceRunning('dbus'))

  @decorators.Enabled('cros-chrome')
  def testGetRemotePortAndIsHTTPServerRunningOnPort(self):
    with self._GetCRI() as cri:
      # Create local server.
      sock = socket.socket()
      sock.bind(('', 0))
      port = sock.getsockname()[1]
      sock.listen(0)

      # Get remote port and ensure that it was unused.
      remote_port = cri.GetRemotePort()
      self.assertFalse(cri.IsHTTPServerRunningOnPort(remote_port))

      # Forward local server's port to remote device's remote_port.
      forwarder = cros_forwarder.CrOsForwarderFactory(cri).Create(
          forwarders.PortPairs(http=forwarders.PortPair(port, remote_port),
                               https=None, dns=None))

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

  @decorators.Enabled('cros-chrome')
  def testGetRemotePortReservedPorts(self):
    with self._GetCRI() as cri:
      # Should return 2 separate ports even though the first one isn't
      # technically being used yet.
      remote_port_1 = cri.GetRemotePort()
      remote_port_2 = cri.GetRemotePort()

      self.assertTrue(remote_port_1 != remote_port_2)

  @decorators.Enabled('cros-chrome')
  def testTakeScreenShot(self):
    with self._GetCRI() as cri:
      def _Cleanup():
        cri.RmRF('/var/log/screenshots/test-prefix*')
      _Cleanup()
      cri.TakeScreenShot('test-prefix')
      self.assertTrue(cri.FileExistsOnDevice(
          '/var/log/screenshots/test-prefix-0.png'))
      _Cleanup()

  # TODO(tengs): It would be best if we can filter this test and other tests
  # that need to be run locally based on the platform of the system browser.
  @decorators.Enabled('linux')
  def testEscapeCmdArguments(self):
    """Commands and their arguments that are executed through the cros
    interface should follow bash syntax. This test needs to run on remotely
    and locally on the device to check for consistency.
    """
    options = options_for_unittests.GetCopy()
    with cros_interface.CrOSInterface(
        options.cros_remote, options.cros_remote_ssh_port,
        options.cros_ssh_identity) as cri:

      # Check arguments with no special characters
      stdout, _ = cri.RunCmdOnDevice(['echo', '--arg1=value1', '--arg2=value2',
          '--arg3="value3"'])
      assert stdout.strip() == '--arg1=value1 --arg2=value2 --arg3=value3'

      # Check argument with special characters escaped
      stdout, _ = cri.RunCmdOnDevice(['echo', '--arg=A\\; echo \\"B\\"'])
      assert stdout.strip() == '--arg=A; echo "B"'

      # Check argument with special characters in quotes
      stdout, _ = cri.RunCmdOnDevice(['echo', "--arg='$HOME;;$PATH'"])
      assert stdout.strip() == "--arg=$HOME;;$PATH"
