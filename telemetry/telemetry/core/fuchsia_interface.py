# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper for common operations on a Fuchsia device"""

import logging
import subprocess

class CommandRunner(object):
  """Helper class used to execute commands on Fuchsia devices on a remote host
  over SSH."""

  def __init__(self, config_path, host, port):
    """Creates a CommandRunner that connects to the specified |host| and |port|
    using the ssh config at the specified |config_path|.

    Args:
      config_path: Full path to SSH configuration.
      host: The hostname or IP address of the remote host.
      port: The port to connect to."""
    self._config_path = config_path
    self._host = host
    self._port = port

  def _GetSshCommandLinePrefix(self):
    return ['ssh', '-F', self._config_path, self._host, '-p', str(self._port)]

  def RunCommandPiped(self, command=None, ssh_args=None, **kwargs):
    """Executes an SSH command on the remote host and returns a process object
    with access to the command's stdio streams. Does not block.

    Args:
      command: A list of strings containing the command and its arguments.
      ssh_args: Arguments that will be passed to SSH.
      kwargs: A dictionary of parameters to be passed to subprocess.Popen().
              The parameters can be used to override stdin and stdout, for
              example.

    Returns:
      A Popen object for the command."""
    if not command:
      command = []
    if not ssh_args:
      ssh_args = []
    ssh_command = self._GetSshCommandLinePrefix() + ssh_args + ['--'] + command
    logging.debug(' '.join(ssh_command))
    return subprocess.Popen(ssh_command, **kwargs)
