#!/usr/bin/env python
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import signal
import sys
import unittest

from devil import devil_env
from devil.android.sdk import adb_wrapper
from devil.utils import cmd_helper
from devil.utils import timeout_retry

_PYMOCK_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir, os.pardir, os.pardir,
    'third_party', 'mock'))
with devil_env.SysPath(_PYMOCK_PATH):
  import mock # pylint: disable=import-error


_ADB_PATH = os.environ.get('ADB_PATH', 'adb')


def _hostAdbPids():
  ps_status, ps_output = cmd_helper.GetCmdStatusAndOutput(
      ['pgrep', '-l', 'adb'])
  if ps_status != 0:
    return []

  pids_and_names = (line.split() for line in ps_output.splitlines())
  return [int(pid) for pid, name in pids_and_names
          if name == 'adb']


@mock.patch('devil.android.sdk.adb_wrapper.AdbWrapper.GetAdbPath',
            return_value=_ADB_PATH)
class AdbCompatibilityTest(unittest.TestCase):

  def testStartServer(self, *_args):
    # Manually kill off any instances of adb.
    adb_pids = _hostAdbPids()
    for p in adb_pids:
      os.kill(p, signal.SIGKILL)

    self.assertIsNotNone(
        timeout_retry.WaitFor(
            lambda: not _hostAdbPids(), wait_period=0.1, max_tries=10))

    # start the adb server
    start_server_status, _ = cmd_helper.GetCmdStatusAndOutput(
        [_ADB_PATH, 'start-server'])

    # verify that the server is now online
    self.assertEquals(0, start_server_status)
    self.assertIsNotNone(
        timeout_retry.WaitFor(
            lambda: bool(_hostAdbPids()), wait_period=0.1, max_tries=10))

  def testKillServer(self, *_args):
    adb_pids = _hostAdbPids()
    if not adb_pids:
      adb_wrapper.AdbWrapper.StartServer()

    adb_pids = _hostAdbPids()
    self.assertEqual(1, len(adb_pids))

    kill_server_status, _ = cmd_helper.GetCmdStatusAndOutput(
        [_ADB_PATH, 'kill-server'])
    self.assertEqual(0, kill_server_status)

    adb_pids = _hostAdbPids()
    self.assertEqual(0, len(adb_pids))

  # TODO(jbudorick): Implement tests for the following:
  # taskset -c
  # devices [-l]
  # push
  # pull
  # shell
  # ls
  # logcat [-c] [-d] [-v] [-b]
  # forward [--remove] [--list]
  # jdwp
  # install [-l] [-r] [-s] [-d]
  # install-multiple [-l] [-r] [-s] [-d] [-p]
  # uninstall [-k]
  # backup -f [-apk] [-shared] [-nosystem] [-all]
  # restore
  # wait-for-device
  # get-state (BROKEN IN THE M SDK)
  # get-devpath
  # remount
  # reboot
  # reboot-bootloader
  # root
  # emu

  @classmethod
  def tearDownClass(cls):
    version_status, version_output = cmd_helper.GetCmdStatusAndOutput(
        [_ADB_PATH, 'version'])
    if version_status != 0:
      version = ['(unable to determine version)']
    else:
      version = version_output.splitlines()

    print
    print 'tested %s' % _ADB_PATH
    for l in version:
      print '  %s' % l


if __name__ == '__main__':
  sys.exit(unittest.main())
