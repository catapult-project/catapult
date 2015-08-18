#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib2
import zipfile

from hooks import install

# URL on omahaproxy.appspot.com which lists cloud storage buckets.
OMAHA_URL = 'https://omahaproxy.appspot.com/all?os=%s&channel=stable'

# URL in cloud storage to download Chrome zip from.
CLOUDSTORAGE_URL = ('https://commondatastorage.googleapis.com/chrome-unsigned'
                    '/desktop-W15K3Y/%s/%s/chrome-%s.zip')

# Default port to run on if not auto-assigning from OS
DEFAULT_PORT = '8111'

# Mapping of sys.platform -> platform-specific names and paths.
PLATFORM_MAPPING = {
    'linux2': {
        'omaha': 'linux',
        'cs_dir': 'precise64',
        'cs_filename': 'precise64',
        'chromepath': 'chrome-precise64/chrome',
        'use_xfvb': True,
    },
    'win32': {
        'omaha': 'win',
        'cs_dir': 'win',
        'cs_filename': 'win',
        'chromepath': 'Chrome-bin\\chrome.exe',
        'installer_url': ('https://commondatastorage.googleapis.com/'
                          'chrome-signed/desktop-W15K3Y/%VERSION%/win/'
                          '%VERSION%_chrome_installer.exe'),
    },
    'darwin': {
        'omaha': 'mac',
        'cs_dir': 'mac64',
        'cs_filename': 'mac',
        'chromepath': ('chrome-mac/Google Chrome.app/'
                       'Contents/MacOS/Google Chrome'),
        'additional_paths': [
            ('chrome-mac/Google Chrome.app/Contents/Versions/%VERSION%/'
             'Google Chrome Helper.app/Contents/MacOS/Google Chrome Helper'),
        ],
    },
}


def StartXvfb():
  display = ':99'
  xvfb_command = [
    'Xvfb',
    display,
    '-screen',
    '0',
    '1024x769x24',
    '-ac'
  ]
  xvfb_process = subprocess.Popen(
      xvfb_command, stdout=open(os.devnull), stderr=open(os.devnull))
  time.sleep(0.2)
  returncode = xvfb_process.poll()
  if returncode is None:
    os.environ['DISPLAY'] = display
  else:
    logging.error('Xvfb did not start, returncode: %s', returncode)
  return xvfb_process


def IsDepotToolsPath(path):
  return os.path.isfile(os.path.join(path, 'gclient'))


def FindDepotTools():
  # Check if depot_tools is already in PYTHONPATH
  for path in sys.path:
    if path.rstrip(os.sep).endswith('depot_tools') and IsDepotToolsPath(path):
      return path

  # Check if depot_tools is in the path
  for path in os.environ['PATH'].split(os.pathsep):
    if IsDepotToolsPath(path):
        return path.rstrip(os.sep)

  return None


def DownloadSignedWinChromeStable(url, version):
  """On Windows, use signed Chrome since it may be more stable."""
  url = url.replace('%VERSION%', version)
  tmpdir = tempfile.mkdtemp()
  installer_path = os.path.join(tmpdir, url[url.rindex('/') + 1:])
  with open(installer_path, 'wb') as local_file:
    local_file.write(urllib2.urlopen(url).read())
  depot_tools_path = FindDepotTools()
  path_7z = os.path.join(depot_tools_path, 'win_toolchain', '7z', '7z.exe')
  command_7z = [path_7z, 'x', '-o' + tmpdir, installer_path]
  process_7z = subprocess.Popen(
    command_7z, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out_7z, err_7z = process_7z.communicate()
  del out_7z, err_7z
  command_7z = [path_7z, 'x', '-o' + tmpdir, os.path.join(tmpdir, 'chrome.7z')]
  process_7z = subprocess.Popen(
    command_7z, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out_7z, err_7z = process_7z.communicate()
  return tmpdir, version


def DownloadChromeStable():
  platform_data = PLATFORM_MAPPING[sys.platform]
  omaha_platform = platform_data['omaha']
  omaha_url = OMAHA_URL % omaha_platform
  response = urllib2.urlopen(omaha_url)
  version = response.readlines()[1].split(',')[2]
  if 'installer_url' in platform_data:
    return DownloadSignedWinChromeStable(
        platform_data['installer_url'], version)
  cs_url = CLOUDSTORAGE_URL % (
      version,
      platform_data['cs_dir'],
      platform_data['cs_filename'])
  tmpdir = tempfile.mkdtemp()
  zip_path = os.path.join(tmpdir, 'chrome.zip')
  with open(zip_path, 'wb') as local_file:
    local_file.write(urllib2.urlopen(cs_url).read())
  zf = zipfile.ZipFile(zip_path)
  zf.extractall(path=tmpdir)
  return tmpdir, version


def GetLocalChromePath(path_from_command_line):
  if path_from_command_line:
    return path_from_command_line

  if sys.platform == 'darwin':  # Mac
    chrome_path = (
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if os.path.isfile(chrome_path):
      return chrome_path
  elif sys.platform.startswith('linux'):
    found = False
    try:
      with open(os.devnull, 'w') as devnull:
        found = subprocess.call(['google-chrome', '--version'],
                                stdout=devnull, stderr=devnull) == 0
    except OSError:
      pass
    if found:
      return 'google-chrome'
  elif sys.platform == 'win32':
    search_paths = [os.getenv('PROGRAMFILES(X86)'),
                    os.getenv('PROGRAMFILES'),
                    os.getenv('LOCALAPPDATA')]
    chrome_path = os.path.join('Google', 'Chrome', 'Application', 'chrome.exe')
    for search_path in search_paths:
      test_path = os.path.join(search_path, chrome_path)
      if os.path.isfile(test_path):
        return test_path
  return None


def Main(argv):
  try:
    parser = argparse.ArgumentParser(
        description='Run dev_server tests for a project.')
    parser.add_argument('--chrome_path', type=str,
                        help='Path to Chrome browser binary.')
    parser.add_argument('--no-use-local-chrome',
                        dest='use_local_chrome', action='store_false')
    parser.add_argument(
        '--no-install-hooks', dest='install_hooks', action='store_false')
    parser.add_argument('--tests', type=str,
                        help='Set of tests to run (tracing or perf_insights)')
    parser.set_defaults(install_hooks=True)
    parser.set_defaults(use_local_chrome=True)
    args = parser.parse_args(argv[1:])

    if args.install_hooks:
      install.InstallHooks()

    platform_data = PLATFORM_MAPPING[sys.platform]
    user_data_dir = tempfile.mkdtemp()
    tmpdir = None
    server_path = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), os.pardir, 'bin', 'run_dev_server')
    # TODO(anniesullie): Make OS selection of port work on Windows. See #1235.
    if sys.platform == 'win32':
      port = DEFAULT_PORT
    else:
      port = '0'
    server_command = [server_path, '--no-install-hooks', '--port', port]
    if sys.platform.startswith('win'):
        server_command = ['python.exe'] + server_command
    server_process = subprocess.Popen(
        server_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=1)
    time.sleep(1)
    if sys.platform != 'win32':
      output = server_process.stderr.readline()
      port = re.search(
          'Now running on http://127.0.0.1:([\d]+)', output).group(1)

    xvfb_process = None
    if args.use_local_chrome:
      chrome_path = GetLocalChromePath(args.chrome_path)
      if not chrome_path:
        logging.error('Could not find path to chrome.')
        sys.exit(1)
    else:
      tmpdir, version = DownloadChromeStable()
      if platform_data.get('use_xfvb'):
        xvfb_process = StartXvfb()
      chrome_path = os.path.join(
          tmpdir, platform_data['chromepath'])
      os.chmod(chrome_path, os.stat(chrome_path).st_mode | stat.S_IEXEC)
      if platform_data.get('additional_paths'):
        for path in platform_data.get('additional_paths'):
          path = path.replace('%VERSION%', version)
          path = os.path.join(tmpdir, path)
          os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    chrome_command = [
        chrome_path,
        '--user-data-dir=%s' % user_data_dir,
        '--no-sandbox',
        '--no-experiments',
        '--no-first-run',
        '--noerrdialogs',
        ('http://localhost:%s/%s/tests.html?' % (port, args.tests)) +
            'headless=true&testTypeToRun=all',
    ]
    chrome_process = subprocess.Popen(
        chrome_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    server_out, server_err = server_process.communicate()
    if sys.platform == 'win32':
      # Use taskkill on Windows to make sure Chrome and all subprocesses are
      # killed.
      subprocess.call(['taskkill', '/F', '/T', '/PID', str(chrome_process.pid)])
    else:
      chrome_process.kill()
    if server_process.returncode != 0:
      logging.error('Tests failed!')
      logging.error('Server stderr:')
      logging.error(server_err)
      logging.error('Server stdout:')
      logging.error(server_out)
    else:
      print server_out
  finally:
    # Wait for Chrome to be killed before deleting temp Chrome dir. Only have
    # this timing issue on Windows.
    if sys.platform == 'win32':
      time.sleep(5)
    if tmpdir:
      try:
        shutil.rmtree(tmpdir)
        shutil.rmtree(user_data_dir)
      except OSError as e:
        logging.error('Error cleaning up temp dirs %s and %s: %s' % (
            tmpdir, user_data_dir, e))
    if xvfb_process:
      xvfb_process.kill()

  sys.exit(server_process.returncode)
