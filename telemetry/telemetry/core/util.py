# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import glob
import imp
import inspect
import logging
import os
import socket
import sys
import time

from telemetry.core import exceptions


def GetBaseDir():
  main_module = sys.modules['__main__']
  if hasattr(main_module, '__file__'):
    return os.path.dirname(os.path.abspath(main_module.__file__))
  else:
    return os.getcwd()


def GetTelemetryDir():
  return os.path.normpath(os.path.join(
      __file__, os.pardir, os.pardir, os.pardir))


def GetUnittestDataDir():
  return os.path.join(GetTelemetryDir(), 'unittest_data')


def GetChromiumSrcDir():
  return os.path.normpath(os.path.join(GetTelemetryDir(), os.pardir, os.pardir))


def AddDirToPythonPath(*path_parts):
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    sys.path.insert(0, path)

_counter = [0]
def _GetUniqueModuleName():
  _counter[0] += 1
  return "page_set_module_" + str(_counter[0])

def GetPythonPageSetModule(file_path):
  return imp.load_source(_GetUniqueModuleName(), file_path)


def WaitFor(condition, timeout):
  """Waits for up to |timeout| secs for the function |condition| to return True.

  Polling frequency is (elapsed_time / 10), with a min of .1s and max of 5s.

  Returns:
    Result of |condition| function (if present).
  """
  min_poll_interval = 0.1
  max_poll_interval = 5
  output_interval = 300

  def GetConditionString():
    if condition.__name__ == '<lambda>':
      try:
        return inspect.getsource(condition).strip()
      except IOError:
        pass
    return condition.__name__

  start_time = time.time()
  last_output_time = start_time
  while True:
    res = condition()
    if res:
      return res
    now = time.time()
    elapsed_time = now - start_time
    last_output_elapsed_time = now - last_output_time
    if elapsed_time > timeout:
      raise exceptions.TimeoutException('Timed out while waiting %ds for %s.' %
                                        (timeout, GetConditionString()))
    if last_output_elapsed_time > output_interval:
      logging.info('Continuing to wait %ds for %s. Elapsed: %ds.',
                   timeout, GetConditionString(), elapsed_time)
      last_output_time = time.time()
    poll_interval = min(max(elapsed_time / 10., min_poll_interval),
                        max_poll_interval)
    time.sleep(poll_interval)


def GetUnreservedAvailableLocalPort():
  """Returns an available port on the system.

  WARNING: This method does not reserve the port it returns, so it may be used
  by something else before you get to use it. This can lead to flake.
  """
  tmp = socket.socket()
  tmp.bind(('', 0))
  port = tmp.getsockname()[1]
  tmp.close()

  return port


def GetBuildDirectories():
  """Yields all combination of Chromium build output directories."""
  build_dirs = ['build',
                os.path.basename(os.environ.get('CHROMIUM_OUT_DIR', 'out')),
                'xcodebuild']

  build_types = ['Debug', 'Debug_x64', 'Release', 'Release_x64']

  for build_dir in build_dirs:
    for build_type in build_types:
      yield build_dir, build_type


def GetSequentialFileName(base_name):
  """Returns the next sequential file name based on |base_name| and the
  existing files. base_name should not contain extension.
  e.g: if base_name is /tmp/test, and /tmp/test_000.json,
  /tmp/test_001.mp3 exist, this returns /tmp/test_002. In case no
  other sequential file name exist, this will return /tmp/test_000
  """
  name, ext = os.path.splitext(base_name)
  assert ext == '', 'base_name cannot contain file extension.'
  index = 0
  while True:
    output_name = '%s_%03d' % (name, index)
    if not glob.glob(output_name + '.*'):
      break
    index = index + 1
  return output_name

def IsRunningOnCrosDevice():
  """Returns True if we're on a ChromeOS device."""
  lsb_release = '/etc/lsb-release'
  if sys.platform.startswith('linux') and os.path.exists(lsb_release):
    with open(lsb_release, 'r') as f:
      res = f.read()
      if res.count('CHROMEOS_RELEASE_NAME'):
        return True
  return False
