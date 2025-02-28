# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
This file provides an interface to the "devil_util_bin" tool located in
chromium/src at //tools/android/devil_util/. See the README.md there for
additional details.
"""

import base64
import gzip
import io
import os

from devil import devil_env
from devil.android import device_errors
from devil.utils import cmd_helper

DEVICE_LIB_PATH = '/data/local/tmp/devil_util'
DEVICE_BIN_PATH = DEVICE_LIB_PATH + '/devil_util_bin'

# We need to cap how many paths we send to the binary at once because
# the ARG_MAX on Android devices is relatively small, typically 131072 bytes.
# However, the more paths we use per invocation, the lower the overhead of
# starting processes, so we want to maximize this number, but we can't compute
# it exactly as we don't know how well our paths will compress.
# 5000 is experimentally determined to be reasonable. 10000 fails, and 7500
# works with existing usage, so 5000 seems like a pretty safe compromise.
_MAX_PATHS_PER_INVOCATION = 5000


def CalculateHostHashes(paths):
  """Calculates a hash for each item in |paths|.

  All items must be files (no directories).

  Args:
    paths: A list of host paths to pass to devil_util.
  Returns:
    A dict mapping file paths to their respective devil_util checksums.
    Missing files exist in the dict, but have '' as values.
  """
  assert isinstance(paths, (list, tuple)), 'Got a ' + type(paths).__name__
  if not paths:
    return {}

  devil_util_bin_host_path = devil_env.config.FetchPath('devil_util_host')
  if not os.path.exists(devil_util_bin_host_path):
    raise IOError('File not built: %s' % devil_util_bin_host_path)

  out = ''
  for i in range(0, len(paths), _MAX_PATHS_PER_INVOCATION):
    mem_file = io.BytesIO()
    compressed = gzip.GzipFile(fileobj=mem_file, mode='wb')
    data = ':'.join(
        [os.path.realpath(p) for p in paths[i:i + _MAX_PATHS_PER_INVOCATION]])
    data = data.encode('utf-8')
    compressed.write(data)
    compressed.close()
    compressed_paths = base64.b64encode(mem_file.getvalue())
    out += cmd_helper.GetCmdOutput(
        [devil_util_bin_host_path, 'hash', compressed_paths])

  return dict(zip(paths, out.splitlines()))


def CalculateDeviceHashes(paths, device):
  """Calculates a hash for each item in |paths|.

  All items must be files (no directories).

  Args:
    paths: A list of device paths to pass to devil_util.
  Returns:
    A dict mapping file paths to their respective devil_util checksums.
    Missing files exist in the dict, but have '' as values.
  """
  assert isinstance(paths, (list, tuple)), 'Got a ' + type(paths).__name__
  if not paths:
    return {}

  devil_util_dist_path = devil_env.config.FetchPath('devil_util_device',
                                                    device=device)

  if os.path.isdir(devil_util_dist_path):
    devil_util_dist_bin_path = os.path.join(devil_util_dist_path,
                                            'devil_util_bin')
  else:
    devil_util_dist_bin_path = devil_util_dist_path

  if not os.path.exists(devil_util_dist_path):
    raise IOError('File not built: %s' % devil_util_dist_path)
  devil_util_file_size = os.path.getsize(devil_util_dist_bin_path)

  # For better performance, make the script as small as possible to try and
  # avoid needing to write to an intermediary file (which RunShellCommand will
  # do if necessary).
  devil_util_script = 'a=%s;' % DEVICE_BIN_PATH
  # Check if the binary is missing or has changed (using its file size as an
  # indicator), and trigger a (re-)push via the exit code.
  devil_util_script += '! [[ $(ls -l $a) = *%d* ]]&&exit 2;' % (
      devil_util_file_size)

  for i in range(0, len(paths), _MAX_PATHS_PER_INVOCATION):
    mem_file = io.BytesIO()
    compressed = gzip.GzipFile(fileobj=mem_file, mode='wb')
    data = ':'.join(paths[i:i + _MAX_PATHS_PER_INVOCATION])
    data = data.encode('utf-8')
    compressed.write(data)
    compressed.close()
    compressed_paths = base64.b64encode(mem_file.getvalue())
    compressed_paths = compressed_paths.decode('utf-8')
    devil_util_script += '$a hash %s;' % compressed_paths

  try:
    # The script can take a bit to run, so use a longer timeout than default.
    out = device.RunShellCommand(devil_util_script,
                                 shell=True,
                                 check_return=True,
                                 large_output=True,
                                 timeout=120)
  except device_errors.AdbShellCommandFailedError as e:
    # Push the binary only if it is found to not exist
    # (faster than checking up-front).
    if e.status == 2:
      # If files were previously pushed as root (adbd running as root), trying
      # to re-push as non-root causes the push command to report success, but
      # actually fail. So, wipe the directory first.
      device.RunShellCommand(['rm', '-rf', DEVICE_LIB_PATH],
                             as_root=True,
                             check_return=True)
      if os.path.isdir(devil_util_dist_path):
        device.adb.Push(devil_util_dist_path, DEVICE_LIB_PATH)
      else:
        mkdir_cmd = 'a=%s;[[ -e $a ]] || mkdir $a' % DEVICE_LIB_PATH
        device.RunShellCommand(mkdir_cmd, shell=True, check_return=True)
        device.adb.Push(devil_util_dist_bin_path, DEVICE_BIN_PATH)
      out = device.RunShellCommand(devil_util_script,
                                   shell=True,
                                   check_return=True,
                                   large_output=True,
                                   timeout=120)
    else:
      raise

  # Filter out linker warnings like
  # 'WARNING: linker: unused DT entry: type 0x1d arg 0x15db'
  return dict(zip(paths, (l for l in out if ' ' not in l)))
