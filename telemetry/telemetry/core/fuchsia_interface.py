# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper for common operations on a Fuchsia device"""

from __future__ import absolute_import
import logging
import os
import platform
import re
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


def GetHostArchFromPlatform():
  host_arch = platform.machine()
  if host_arch in ['x86_64', 'AMD64']:
    return 'x64'
  if host_arch in ['arm64', 'aarch64']:
    return 'arm64'
  raise Exception('Unsupported host architecture: %s' % host_arch)


_FFX_TOOL = os.path.join(
    SDK_ROOT, 'tools', GetHostArchFromPlatform(), 'ffx')


def _run_repair_command(output):
  """Scans |output| for a self-repair command to run and, if found, runs it.

  Returns:
    True if a repair command was found and ran successfully. False otherwise.
  """

  # Check for a string along the lines of:
  # "Run `ffx doctor --restart-daemon` for further diagnostics."
  match = re.search('`ffx ([^`]+)`', output)
  if not match or len(match.groups()) != 1:
    return False  # No repair command found.
  args = match.groups()[0].split()

  try:
    run_ffx_command(args, suppress_repair=True)
  except subprocess.CalledProcessError:
    return False  # Repair failed.
  return True  # Repair succeeded.


def run_ffx_command(cmd, target_id = None, check = True,
                    suppress_repair = False, **kwargs):
  """Runs `ffx` with the given arguments, waiting for it to exit.

  If `ffx` exits with a non-zero exit code, the output is scanned for a
  recommended repair command (e.g., "Run `ffx doctor --restart-daemon` for
  further diagnostics."). If such a command is found, it is run and then the
  original command is retried. This behavior can be suppressed via the
  `suppress_repair` argument.

  Args:
      cmd: A sequence of arguments to ffx.
      target_id: Whether to execute the command for a specific target. The
            target_id could be in the form of a nodename or an address.
      check: If True, CalledProcessError is raised if ffx returns a non-zero
          exit code.
      suppress_repair: If True, do not attempt to find and run a repair
          command.
  Returns:
      A CompletedProcess instance
  Raises:
      CalledProcessError if |check| is true.
  """

  ffx_cmd = [_FFX_TOOL]
  if target_id:
    ffx_cmd.extend(('--target', target_id))
  ffx_cmd.extend(cmd)
  try:
    return subprocess.run(ffx_cmd, check=check, encoding='utf-8', **kwargs)
  except subprocess.CalledProcessError as cpe:
    if suppress_repair or not _run_repair_command(cpe.output):
      raise

  # If the original command failed but a repair command was found and
  # succeeded, try one more time with the original command.
  return run_ffx_command(cmd, target_id, check, True, **kwargs)


def run_continuous_ffx_command(cmd, target_id, **kwargs):
  """Runs an ffx command asynchronously."""

  ffx_cmd = [_FFX_TOOL]
  ffx_cmd.extend(('--target', target_id))
  ffx_cmd.extend(cmd)
  return subprocess.Popen(ffx_cmd, encoding='utf-8', **kwargs)


class CommandRunner():
  """Helper class used to execute commands on Fuchsia devices on a remote host
  over SSH."""

  def __init__(self, config_path, host, port, target_id=None):
    """Creates a CommandRunner that connects to the specified |host| and |port|
    using the ssh config at the specified |config_path|.

    Args:
      config_path: Full path to SSH configuration.
      host: The hostname or IP address of the remote host.
      port: The port to connect to.
      target_id: The target id used by ffx."""
    self._config_path = config_path
    self._host = host
    self._port = port

    def format_host_port(host, port):
      """Formats a host name or IP address and port number into a host:port
      string. """

      if not port:
        return host

      # Convert localhost to IPv4 address.
      if host == 'localhost':
        host = '127.0.0.1'

      # Wrap `host` in brackets if it looks like an IPv6 address.
      return ('[%s]:%d' if ':' in host else '%s:%d') % (host, port)

    self._target_id = target_id or format_host_port(host, port)

  @property
  def host(self):
    return self._host

  def _GetSshCommandLinePrefix(self):
    prefix_cmd = ['ssh', '-F', self._config_path, self._host]
    if self._port:
      prefix_cmd += ['-p', str(self._port)]
    return prefix_cmd

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


def StartSymbolizerForProcessIfPossible(input_file, output_file,
                                        build_id_files):
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
