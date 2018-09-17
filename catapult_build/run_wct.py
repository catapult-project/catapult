# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import subprocess
import tempfile

from catapult_build import run_dev_server_tests
from py_utils import binary_manager
from py_utils import dependency_util
from py_utils import xvfb


def RunWct(base_dir, dep_dirs, persist=False, chrome_channel='stable'):
  wct_bin = os.environ.get('WCT', 'wct')
  if os.system('which %s > /dev/null' % wct_bin):
    print 'FATAL ERROR: wct not found. Install it and add it to your path:'
    print 'cipd install -root ~/cipd infra/testing/wct/linux-amd64 prod'
    print 'export PATH=~/cipd:$PATH'
    return 1

  xvfb_process = None

  chrome_bin = run_dev_server_tests.GetLocalChromePath(None)
  if not chrome_bin:
    chrome_manager = binary_manager.BinaryManager([
        run_dev_server_tests.CHROME_BINARIES_CONFIG])
    arch, os_name = dependency_util.GetOSAndArchForCurrentDesktopPlatform()
    chrome_bin = chrome_manager.FetchPathWithVersion(
        'chrome_%s' % chrome_channel, arch, os_name)[0]
    if not chrome_bin or os.system('which %s > /dev/null' % chrome_bin):
      print 'FATAL ERROR: chrome not found.'
      return 1

    if xvfb.ShouldStartXvfb():
      print 'Starting xvfb...'
      xvfb_process = xvfb.StartXvfb()

  user_data_dir = tempfile.mkdtemp()

  command = [wct_bin]
  command += ['-chrome', chrome_bin]
  command += ['-dir', user_data_dir]
  command += ['-base', base_dir]
  if persist:
    command += ['-persist']
  for dep in dep_dirs:
    command += ['-dep', dep]
  logging.info('Starting WCT: %r', command)

  try:
    return subprocess.call(command)
  finally:
    if xvfb_process:
      xvfb_process.kill()
    try:
      shutil.rmtree(user_data_dir)
    except OSError as e:
      logging.error('Error cleaning up temp dir %r: %s',
                    user_data_dir, e)
