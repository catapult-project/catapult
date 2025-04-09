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
import itertools
import os
import tempfile

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
    raise FileNotFoundError('File not built: %s' % devil_util_bin_host_path)

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
    exit_code, stdout, stderr = cmd_helper.GetCmdStatusOutputAndError(
        [devil_util_bin_host_path, 'hash', compressed_paths])
    if exit_code != 0:
      break
    out += stdout

  if exit_code != 0:
    exc_msg = ['Failed to hash files']
    exc_msg.extend('stdout: %s' % l for l in stdout.splitlines())
    exc_msg.extend('stderr: %s' % l for l in stderr.splitlines())
    raise device_errors.CommandFailedError(os.linesep.join(exc_msg))

  return dict(zip(paths, out.splitlines()))


def CreateZstCompressedArchive(archive_path, archive_members):
  """Create a zst-compressed archive file on the host.

  Args:
    archive_path: The path to the zst-compressed archive that will be created.
    archive_members: A list of (host_path, archive_path) tuples,
      where |host_path| is an absolute path of a file in the host machine,
      and |archive_path| is an absolute path of the file in the archive.
      In other words, we read the file at |host_path| and store it in the
      archive, and we put the file to |archive_path| when it is extracted.
  """
  devil_util_bin_host_path = devil_env.config.FetchPath('devil_util_host')
  if not os.path.exists(devil_util_bin_host_path):
    raise FileNotFoundError('File not built: %s' % devil_util_bin_host_path)

  # The format of the archive members file is defined at
  # //tools/android/devil_util/main.cc
  with tempfile.NamedTemporaryFile(suffix='.txt',
                                   mode='w') as archive_members_file:
    flattened_archive_members = itertools.chain.from_iterable(archive_members)
    lines_to_write = [
        member + os.linesep for member in flattened_archive_members
    ]
    archive_members_file.writelines(lines_to_write)
    archive_members_file.flush()
    exit_code, stdout, stderr = cmd_helper.GetCmdStatusOutputAndError([
        devil_util_bin_host_path, 'archive', archive_path,
        archive_members_file.name
    ])

  if exit_code != 0:
    exc_msg = ['Failed to create %s' % archive_path]
    exc_msg.extend('stdout: %s' % l for l in stdout.splitlines())
    exc_msg.extend('stderr: %s' % l for l in stderr.splitlines())
    raise device_errors.CommandFailedError(os.linesep.join(exc_msg))


def _RunDevilUtilOnDevice(devil_util_cmd, device, large_output=False):
  """Run the devil_util binary on the device,

  Args:
    devil_util_cmd: The devil_util command that needs to be run.
      Can replace the actual path to the devil_util binary with $a.
    large_output: Whether this command will produce a large amount of output.
  Returns:
    The output of the devil_util command.
  """
  devil_util_dist_path = devil_env.config.FetchPath('devil_util_device',
                                                    device=device)
  if not os.path.exists(devil_util_dist_path):
    raise FileNotFoundError('File not built: %s' % devil_util_dist_path)

  if os.path.isdir(devil_util_dist_path):
    devil_util_dist_bin_path = os.path.join(devil_util_dist_path,
                                            'devil_util_bin')
  else:
    devil_util_dist_bin_path = devil_util_dist_path
  devil_util_file_size = os.path.getsize(devil_util_dist_bin_path)

  # For better performance, make the script as small as possible to try and
  # avoid needing to write to an intermediary file (which RunShellCommand will
  # do if necessary).
  devil_util_script = 'a=%s;' % DEVICE_BIN_PATH
  # Check if the binary is missing or has changed (using its file size as an
  # indicator), and trigger a (re-)push via the exit code.
  devil_util_script += '! [[ $(ls -l $a) = *%d* ]]&&exit 2;' % (
      devil_util_file_size)
  devil_util_script += devil_util_cmd

  try:
    out = device.RunShellCommand(devil_util_script,
                                 shell=True,
                                 check_return=True,
                                 as_root=True,
                                 large_output=large_output,
                                 timeout=120)
  except device_errors.AdbCommandFailedError as e:
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
                                   as_root=True,
                                   large_output=large_output,
                                   timeout=120)
    else:
      raise

  return out


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

  devil_util_cmd = ''
  for i in range(0, len(paths), _MAX_PATHS_PER_INVOCATION):
    mem_file = io.BytesIO()
    compressed = gzip.GzipFile(fileobj=mem_file, mode='wb')
    data = ':'.join(paths[i:i + _MAX_PATHS_PER_INVOCATION])
    data = data.encode('utf-8')
    compressed.write(data)
    compressed.close()
    compressed_paths = base64.b64encode(mem_file.getvalue())
    compressed_paths = compressed_paths.decode('utf-8')
    devil_util_cmd += '$a hash %s;' % compressed_paths
  out = _RunDevilUtilOnDevice(devil_util_cmd, device, large_output=True)

  # Filter out linker warnings like
  # 'WARNING: linker: unused DT entry: type 0x1d arg 0x15db'
  return dict(zip(paths, (l for l in out if ' ' not in l)))


def ExtractZstCompressedArchive(archive_path, device):
  """Extract a zst-compressed archive located at |archive_path| on the device.

  Args:
    archive_path: The path to the zst-compressed archive file on the device.
  """
  devil_util_cmd = '$a extract %s' % archive_path
  _RunDevilUtilOnDevice(devil_util_cmd, device)


def CreateNamedPipe(named_pipe_path, device):
  """Create a named pipe at |named_pipe_path| on the device via mkfifo syscall.

  Args:
    named_pipe_path: The path to the named pipe that will be created.
  """
  devil_util_cmd = '$a pipe %s' % named_pipe_path
  _RunDevilUtilOnDevice(devil_util_cmd, device)
