# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
This file provides an interface to the "devil_util_bin" tool located in
chromium/src at //tools/android/devil_util/. See the README.md there for
additional details.
"""

import collections
import itertools
import logging
import os
import tempfile
import threading

from devil import devil_env
from devil.android import device_errors
from devil.android import device_temp_file
from devil.utils import cmd_helper

DEVICE_BIN_PATH = '/data/local/tmp/devil_util_bin'

# We need to cap how many paths we send to the binary at once because
# the ARG_MAX on Android devices is relatively small, typically 131072 bytes.
# Therefore, if there are too many paths, we should not pass the paths to the
# binary as command line arguments. We should instead write the paths to a file,
# push the file to the device, and ask the binary to read from the file.
# Moreover, if the length of the command is more than 512, RunShellCommand()
# will write the command to a file, push the file to the device, and then
# execute the file containing the command. This means that if the length of all
# file paths is more than 512, we are better off creating and pushing the file
# ourselves instead of relying on RunShellCommand() to create and push the file.
# Finally, we reduce the max length from 512 to 400, to compensate for the fact
# that the command contains more than just the file paths.
_MAX_FILE_PATHS_LENGTH = 400


# Lock to hold when checking the "by_serial" dicts below.
_update_bin_main_lock = threading.Lock()

# Lock to hold when updating /data/local/tmp/devil_util_bin.
_update_bin_lock_by_serial = collections.defaultdict(threading.Lock)

# Counts the number of times devil_util_bin has been pushed per device.
_update_bin_attempts_by_serial = collections.defaultdict(int)


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

  combined_paths = ':'.join([os.path.realpath(p) for p in paths])
  if len(combined_paths) > _MAX_FILE_PATHS_LENGTH:
    with tempfile.NamedTemporaryFile(suffix='.zst') as compressed_arg_file:
      CompressViaZst(compressed_arg_file.name, combined_paths)
      exit_code, stdout, stderr = cmd_helper.GetCmdStatusOutputAndError(
          [devil_util_bin_host_path, 'hash',
           '@%s' % compressed_arg_file.name])
  else:
    combined_paths_escaped = cmd_helper.SingleQuote(combined_paths)
    exit_code, stdout, stderr = cmd_helper.GetCmdStatusOutputAndError(
        [devil_util_bin_host_path, 'hash', combined_paths_escaped])

  if exit_code != 0:
    exc_msg = ['Failed to hash files']
    exc_msg.extend('stdout: %s' % l for l in stdout.splitlines())
    exc_msg.extend('stderr: %s' % l for l in stderr.splitlines())
    raise device_errors.CommandFailedError(os.linesep.join(exc_msg))

  return dict(zip(paths, stdout.splitlines()))


def CompressViaZst(compressed_path, uncompressed_content):
  """Compress given content via zst and write to the specified file on the host.

  Args:
    compressed_path: The path to the file that will contain the compressed
      content after the execution of this function.
    uncompressed_content: The content that will be compressed.
  """
  devil_util_bin_host_path = devil_env.config.FetchPath('devil_util_host')
  if not os.path.exists(devil_util_bin_host_path):
    raise FileNotFoundError('File not built: %s' % devil_util_bin_host_path)

  with tempfile.NamedTemporaryFile(mode='w') as uncompressed_content_file:
    uncompressed_content_file.write(uncompressed_content)
    uncompressed_content_file.flush()
    exit_code, stdout, stderr = cmd_helper.GetCmdStatusOutputAndError([
        devil_util_bin_host_path, 'compress', compressed_path,
        '@%s' % uncompressed_content_file.name
    ])

  if exit_code != 0:
    exc_msg = ['Failed to compress %s (truncated)' % uncompressed_content[:100]]
    exc_msg.extend('stdout: %s' % l for l in stdout.splitlines())
    exc_msg.extend('stderr: %s' % l for l in stderr.splitlines())
    raise device_errors.CommandFailedError(os.linesep.join(exc_msg))


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
    devil_util_dist_path = os.path.join(devil_util_dist_path, 'devil_util_bin')
    if not os.path.exists(devil_util_dist_path):
      raise IOError('File not built: %s' % devil_util_dist_path)

  devil_util_file_size = os.path.getsize(devil_util_dist_path)

  # For better performance, make the script as small as possible to try and
  # avoid needing to write to an intermediary file (which RunShellCommand will
  # do if necessary).
  devil_util_script = 'a=%s;' % DEVICE_BIN_PATH
  # Check if the binary is missing or has changed (using its file size as an
  # indicator), and trigger a (re-)push via the exit code.
  devil_util_script += '! [[ $(ls -l $a) = *%d* ]]&&exit 2;' % (
      devil_util_file_size)
  devil_util_script += devil_util_cmd

  with _update_bin_main_lock:
    prev_push_attempts = _update_bin_attempts_by_serial[device.serial]

  def attempt_command():
    return device.RunShellCommand(devil_util_script,
                                  shell=True,
                                  check_return=True,
                                  as_root=True,
                                  large_output=large_output,
                                  timeout=120)

  try:
    out = attempt_command()
  except device_errors.AdbCommandFailedError as e:
    # Push the binary only if it is found to not exist
    # (faster than checking up-front).
    if e.status != 2:
      raise

    with _update_bin_main_lock:
      update_lock = _update_bin_lock_by_serial[device.serial]
    with update_lock:
      with _update_bin_main_lock:
        cur_push_attempts = _update_bin_attempts_by_serial[device.serial]
      # Check if another thread updated it for us.
      if prev_push_attempts == cur_push_attempts:
        logging.info('Updating devil_util_bin')
        # If files were previously pushed as root (adbd running as root), trying
        # to re-push as non-root causes the push command to report success, but
        # actually fail. So, wipe the directory first.
        device.RunShellCommand(['rm', '-rf', DEVICE_BIN_PATH],
                               as_root=True,
                               check_return=True)
        device.adb.Push(devil_util_dist_path, DEVICE_BIN_PATH)
        with _update_bin_main_lock:
          _update_bin_attempts_by_serial[device.serial] += 1
      else:
        logging.info('Another thread updated devil_util_bin')

    # Retry the command
    out = attempt_command()

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

  combined_paths = ':'.join(paths)
  if len(combined_paths) > _MAX_FILE_PATHS_LENGTH:
    with device_temp_file.DeviceTempFile(device.adb,
                                         suffix='.zst') as compressed_arg_file:
      with tempfile.NamedTemporaryFile(suffix='.zst') as host_temp_file:
        CompressViaZst(host_temp_file.name, combined_paths)
        device.adb.Push(host_temp_file.name, compressed_arg_file.name)
      devil_util_cmd = '$a hash @%s' % compressed_arg_file.name
      out = _RunDevilUtilOnDevice(devil_util_cmd, device, large_output=True)
  else:
    combined_paths_escaped = cmd_helper.SingleQuote(combined_paths)
    devil_util_cmd = "$a hash %s" % combined_paths_escaped
    out = _RunDevilUtilOnDevice(devil_util_cmd, device)

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
