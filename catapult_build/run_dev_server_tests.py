#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import json
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

from catapult_base import xvfb

# URL on omahaproxy.appspot.com which lists the current version for the os
# and channel.
VERSION_LOOKUP_URL = 'https://omahaproxy.appspot.com/all?os=%s&channel=%s'

# URL on omahaproxy.appspot.com which looks up base positions from versions.
BASE_POS_LOOKUP_URL = 'http://omahaproxy.appspot.com/revision.json?version=%s'

# URL on cloud storage which looks up the chromium download url from base pos.
CLOUD_STORAGE_LOOKUP_URL = ('https://www.googleapis.com/storage/v1/b/'
                            'chromium-browser-snapshots/o?delimiter=/&prefix='
                            '%s/%s&fields=items(kind,mediaLink,metadata,name,'
                            'size,updated),kind,prefixes,nextPageToken')

# URL on cloud storage to download chromium at a base pos from.
CLOUD_STORAGE_DOWNLOAD_URL = ('https://www.googleapis.com/download/storage/v1/b'
                              '/chromium-browser-snapshots/o/%s%%2F%s%%2F'
                              'chrome-%s.zip?alt=media')

# URL in cloud storage to download Chrome zip from.
CLOUDSTORAGE_URL = ('https://commondatastorage.googleapis.com/chrome-unsigned'
                    '/desktop-W15K3Y/%s/%s/chrome-%s.zip')

# Default port to run on if not auto-assigning from OS
DEFAULT_PORT = '8111'

# Mapping of sys.platform -> platform-specific names and paths.
PLATFORM_MAPPING = {
    'linux2': {
        'omaha': 'linux',
        'prefix': 'Linux_x64',
        'zip_prefix': 'linux',
        'chromepath': 'chrome-linux/chrome'
    },
    'win32': {
        'omaha': 'win',
        'prefix': 'Win',
        'zip_prefix': 'win32',
        'chromepath': 'chrome-win32\\chrome.exe',
    },
    'darwin': {
        'omaha': 'mac',
        'prefix': 'Mac',
        'zip_prefix': 'mac',
        'chromepath': ('chrome-mac/Chromium.app/Contents/MacOS/Chromium'),
        'version_path': 'chrome-mac/Chromium.app/Contents/Versions/',
        'additional_paths': [
            ('chrome-mac/Chromium.app/Contents/Versions/%VERSION%/'
             'Chromium Helper.app/Contents/MacOS/Chromium Helper'),
        ],
    },
}


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


def DownloadChromium(channel):
  """
  Gets the version of Chrome current for the given channel from omahaproxy, then
  follows instructions for downloading a prebuilt version of chromium from the
  commit at the branch cut for that version. This downloads a chromium binary
  which does not have any commits merged onto the branch. It is close to the
  released Chrome, but not exact. Downloading the released Chrome is not
  supported.
  https://www.chromium.org/getting-involved/download-chromium
  """
  # Get the version for the current channel from omahaproxy
  platform_data = PLATFORM_MAPPING[sys.platform]
  omaha_platform = platform_data['omaha']
  version_lookup_url = VERSION_LOOKUP_URL % (omaha_platform, channel)
  print 'Getting version from %s' % version_lookup_url
  response = urllib2.urlopen(version_lookup_url, timeout=120)
  version = response.readlines()[1].split(',')[2]

  # Get the base position for that version from omahaproxy
  base_pos_lookup_url = BASE_POS_LOOKUP_URL % version
  print 'Getting base_pos from %s' % base_pos_lookup_url
  response = urllib2.urlopen(base_pos_lookup_url, timeout=120)
  base_pos = json.load(response)['chromium_base_position']

  # Find the build from that base position in cloud storage. If it's not found,
  # decrement base position until one is found.
  cloud_storage_lookup_url = CLOUD_STORAGE_LOOKUP_URL % (
      platform_data['prefix'], base_pos)
  download_url = None
  while not download_url:
    print 'Getting download url from %s' % cloud_storage_lookup_url
    response = urllib2.urlopen(cloud_storage_lookup_url, timeout=120)
    prefixes = json.load(response).get('prefixes')
    if prefixes:
      download_url = CLOUD_STORAGE_DOWNLOAD_URL % (
          platform_data['prefix'], base_pos, platform_data['zip_prefix'])
      break
    base_pos = int(base_pos) - 1
    cloud_storage_lookup_url = CLOUD_STORAGE_LOOKUP_URL % (
        platform_data['prefix'], base_pos)

  print 'Approximating Chrome %s with chromium from base position %s.' % (
      version, base_pos)
  print 'Downloading from %s' % download_url

  tmpdir = tempfile.mkdtemp()
  zip_path = os.path.join(tmpdir, 'chrome.zip')
  with open(zip_path, 'wb') as local_file:
    local_file.write(urllib2.urlopen(download_url, timeout=600).read())
  zf = zipfile.ZipFile(zip_path)
  zf.extractall(path=tmpdir)
  return tmpdir, version, download_url


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
    parser.add_argument('--channel', type=str, default='stable',
                        help='Chrome channel to run (stable or canary)')
    parser.add_argument('--presentation-json', type=str,
                        help='Recipe presentation-json output file path')
    parser.set_defaults(install_hooks=True)
    parser.set_defaults(use_local_chrome=True)
    args = parser.parse_args(argv[1:])

    if args.install_hooks:
      install.InstallHooks()

    platform_data = PLATFORM_MAPPING[sys.platform]
    user_data_dir = tempfile.mkdtemp()
    tmpdir = None
    xvfb_process = None

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
    print "Starting dev_server..."
    server_process = subprocess.Popen(
        server_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=1)
    time.sleep(1)
    if sys.platform != 'win32':
      output = server_process.stderr.readline()
      port = re.search(
          r'Now running on http://127.0.0.1:([\d]+)', output).group(1)

    chrome_info = None
    if args.use_local_chrome:
      chrome_path = GetLocalChromePath(args.chrome_path)
      if not chrome_path:
        logging.error('Could not find path to chrome.')
        sys.exit(1)
      chrome_info = 'with command `%s`' % chrome_path
    else:
      channel = args.channel
      if sys.platform == 'linux2' and channel == 'canary':
        channel = 'dev'
      assert channel in ['stable', 'beta', 'dev', 'canary']


      tmpdir, version, download_url = DownloadChromium(channel)
      if xvfb.ShouldStartXvfb():
        xvfb_process = xvfb.StartXvfb()
      chrome_path = os.path.join(
          tmpdir, platform_data['chromepath'])
      os.chmod(chrome_path, os.stat(chrome_path).st_mode | stat.S_IEXEC)
      # On Mac, we need to update a file with the version in the path, and
      # the version we downloaded could be slightly different than what we
      # requested. Update it.
      if platform_data.get('version_path'):
        contents = os.listdir(
            os.path.join(tmpdir, platform_data['version_path']))
        for path in contents:
          if re.match(r'\d+\.\d+\.\d+\.\d+', path):
            version = path
      if platform_data.get('additional_paths'):
        for path in platform_data.get('additional_paths'):
          path = path.replace('%VERSION%', version)
          path = os.path.join(tmpdir, path)
          if os.path.exists(path):
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
      chrome_info = version
    chrome_command = [
        chrome_path,
        '--user-data-dir=%s' % user_data_dir,
        '--no-sandbox',
        '--no-experiments',
        '--no-first-run',
        '--noerrdialogs',
        '--window-size=1280,1024',
        ('http://localhost:%s/%s/tests.html?' % (port, args.tests)) +
        'headless=true&testTypeToRun=all',
    ]
    print "Starting Chrome %s..." % chrome_info
    chrome_process = subprocess.Popen(
        chrome_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print "Waiting for tests to finish..."
    server_out, server_err = server_process.communicate()
    print "Killing Chrome..."
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
    if args.presentation_json:
      with open(args.presentation_json, 'w') as recipe_out:
        # Add a link to the buildbot status for the step saying which version
        # of Chrome the test ran on. The actual linking feature is not used,
        # but there isn't a way to just add text.
        link_name = 'Chrome Version %s' % version
        presentation_info = {'links': {link_name: download_url}}
        json.dump(presentation_info, recipe_out)
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
        logging.error('Error cleaning up temp dirs %s and %s: %s',
                      tmpdir, user_data_dir, e)
    if xvfb_process:
      xvfb_process.kill()

  sys.exit(server_process.returncode)
