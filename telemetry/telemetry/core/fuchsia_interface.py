# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper for common operations on a Fuchsia device"""

from __future__ import absolute_import
import logging
import os
import platform
import subprocess

# TODO(crbug.com/1267066): Remove when python2 is deprecated.
import six

from telemetry.core import util

FUCHSIA_BROWSERS = [
    'fuchsia-chrome',
    'web-engine-shell',
    'cast-streaming-shell',
]

_SDK_ROOT_IN_CATAPULT = os.path.join(util.GetCatapultDir(), 'third_party',
                                     'fuchsia-sdk', 'sdk')
_SDK_ROOT_IN_CHROMIUM = os.path.join(util.GetCatapultDir(), '..',
                                     'fuchsia-sdk', 'sdk')
if os.path.exists(_SDK_ROOT_IN_CHROMIUM):
  SDK_ROOT = _SDK_ROOT_IN_CHROMIUM
else:
  SDK_ROOT = _SDK_ROOT_IN_CATAPULT


class CommandRunner(object):
  """Helper class used to execute commands on Fuchsia devices on a remote host
  over SSH."""

  def __init__(self, config_path, host, port, node_name=None):
    """Creates a CommandRunner that connects to the specified |host| and |port|
    using the ssh config at the specified |config_path|. Provides
    optional |node_name| to indicate name of Fuchsia target.

    Args:
      config_path: Full path to SSH configuration.
      host: The hostname or IP address of the remote host.
      port: The port to connect to.
      node_name: Optional node-name of fuchsia target."""
    self._config_path = config_path
    self._host = host
    self._port = port
    self._node_name = node_name

  @property
  def node_name(self):
    return self._node_name

  @property
  def host(self):
    return self._host

  def _GetSshCommandLinePrefix(self):
    prefix_cmd = ['ssh', '-F', self._config_path, self._host]
    if self._port:
      prefix_cmd += ['-p', str(self._port)]
    return prefix_cmd

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

    # Having control master causes weird behavior in port_forwarding.
    ssh_args.append('-oControlMaster=no')
    ssh_command = self._GetSshCommandLinePrefix() + ssh_args + ['--'] + command
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


def GetHostArchFromPlatform():
  host_arch = platform.machine()
  if host_arch in ['x86_64', 'AMD64']:
    return 'x64'
  if host_arch in ['arm64', 'aarch64']:
    return 'arm64'
  raise Exception('Unsupported host architecture: %s' % host_arch)


def StartSymbolizerForProcessIfPossible(input_file, output_file, build_id_files):
  """Starts a symbolizer process if possible.

    Args:
      input_file: Input file to be symbolized.
      output_file: Output file for symbolizer stdout and stderr.
      build_id_files: Path to the ids.txt files which maps build IDs to
          unstripped binaries on the filesystem.

    Returns:
      A subprocess.Popen object for the started process, None if symbolizer
      fails to start."""
  if build_id_files:
    symbolizer = os.path.join(SDK_ROOT, 'tools', GetHostArchFromPlatform(),
                              'symbolizer')
    symbolizer_cmd = [
        symbolizer, '--build-id-dir', os.path.join(SDK_ROOT, '.build-id')
    ]

    for build_id_file in build_id_files:
      if not os.path.isfile(build_id_file):
        logging.error(
            'Symbolizer cannot be started. %s is not a file' % build_id_file)
        return None
      symbolizer_cmd.extend(['--ids-txt', build_id_file])

    logging.debug('Running "%s".' % ' '.join(symbolizer_cmd))
    kwargs = {
        'stdin':input_file,
        'stdout':output_file,
        'stderr':subprocess.STDOUT,
        'close_fds':True
    }
    if six.PY3:
      kwargs['text'] = True
    return subprocess.Popen(symbolizer_cmd, **kwargs)
  logging.error('Symbolizer cannot be started.')
  return None
