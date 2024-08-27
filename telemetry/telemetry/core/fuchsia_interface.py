# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper for common operations on a Fuchsia device"""

from __future__ import absolute_import
import logging
import os
import subprocess
import sys

# TODO(crbug.com/1267066): Remove when python2 is deprecated.
import six

from telemetry.core import util

TEST_SCRIPTS_ROOT = os.path.join(util.GetCatapultDir(), '..', '..', 'build',
                                 'fuchsia', 'test')

# The path is dynamically included since the fuchsia runner modules are not
# always available, and other platforms shouldn't depend on the fuchsia
# runners.
# pylint: disable=import-error,import-outside-toplevel


def include_fuchsia_package():
  if TEST_SCRIPTS_ROOT in sys.path:
    # The import should happen exactly once.
    return
  assert os.path.exists(TEST_SCRIPTS_ROOT), \
         "Telemetry support on Fuchsia currently requires a Chromium checkout."
  sys.path.insert(0, TEST_SCRIPTS_ROOT)


FUCHSIA_BROWSERS = [
    'web-engine-shell',
    'cast-streaming-shell',
]

FUCHSIA_REPO = 'fuchsia.com'


def run_ffx_command(cmd, target_id=None, check=True, **kwargs):
  # TODO(crbug.com/40935291): Remove this function in favor of using
  # common.run_ffx_command directly.
  include_fuchsia_package()
  from common import run_ffx_command as ffx_run
  return ffx_run(check=check, cmd=cmd, target_id=target_id, **kwargs)


def run_continuous_ffx_command(cmd, target_id, **kwargs):
  # TODO(crbug.com/40935291): Remove this function in favor of using
  # common.run_continuous_ffx_command directly.
  include_fuchsia_package()
  from common import run_continuous_ffx_command as ffx_run_continuous
  return ffx_run_continuous(cmd=cmd, target_id=target_id, **kwargs)


class CommandRunner():
  """Helper class used to execute commands on Fuchsia devices on a remote host
  over SSH."""

  def __init__(self, target_id):
    """Creates a CommandRunner that connects to the specified |host| and |port|
    using the ssh config at the specified |config_path|.

    Args:
      target_id: The target id used by ffx."""
    self._target_id = target_id
    include_fuchsia_package()
    from common import get_ssh_address
    from compatible_utils import get_ssh_prefix
    self._ssh_prefix = get_ssh_prefix(get_ssh_address(target_id))

  def run_ffx_command(self, cmd, **kwargs):
    return run_ffx_command(cmd, self._target_id, **kwargs)

  def run_continuous_ffx_command(self, cmd, **kwargs):
    return run_continuous_ffx_command(cmd, self._target_id, **kwargs)

  def RunCommandPiped(self, command=None, ssh_args=None, **kwargs):
    """Executes an SSH command on the remote host and returns a process object
    with access to the command's stdio streams. Does not block.

    Args:
      command: A list of strings containing the command and its arguments.
      ssh_args: Arguments that will be passed to SSH.
      kwargs: A dictionary of parameters to be passed to subprocess.Popen().
          The parameters can be used to override stdin and stdout, for example.

    Returns:
      A subprocess.Popen object for the command."""
    if not command:
      command = []
    if not ssh_args:
      ssh_args = []

    ssh_command = self._ssh_prefix + ssh_args + ['--'] + command
    logging.debug(' '.join(ssh_command))
    if six.PY3:
      kwargs['text'] = True
    return subprocess.Popen(ssh_command, **kwargs)

  def RunCommand(self, command=None, ssh_args=None, **kwargs):
    """Executes an SSH command on the remote host and returns stdout, stderr,
    and return code of the command. Blocks."""
    cmd_proc = self.RunCommandPiped(command, ssh_args, **kwargs)
    stdout, stderr = cmd_proc.communicate()
    return cmd_proc.returncode, stdout, stderr

  @property
  def target_id(self) -> str:
    return self._target_id


# TODO(crbug.com/40935291): This function shouldn't return None and the name
# suffix 'IfPossible' should be removed.
def StartSymbolizerForProcessIfPossible(input_file, output_file,
                                        build_id_files):
  """Starts a symbolizer process.

    Args:
      input_file: Input file to be symbolized.
      output_file: Output file for symbolizer stdout and stderr.
      build_id_files: Path to the ids.txt files which maps build IDs to
          unstripped binaries on the filesystem.

    Returns:
      A subprocess.Popen object for the started process, None if symbolizer
      fails to start."""
  include_fuchsia_package()
  from ffx_integration import run_symbolizer
  return run_symbolizer(build_id_files, input_file, output_file)
