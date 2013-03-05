# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper around ssh for common operations on a CrOS-based device"""
import logging
import os
import re
import subprocess
import sys
import time
import tempfile

from telemetry.core import util

# TODO(nduca): This whole file is built up around making individual ssh calls
# for each operation. It really could get away with a single ssh session built
# around pexpect, I suspect, if we wanted it to be faster. But, this was
# convenient.

def RunCmd(args, cwd=None, quiet=False):
  """Opens a subprocess to execute a program and returns its return value.

  Args:
    args: A string or a sequence of program arguments. The program to execute is
      the string or the first item in the args sequence.
    cwd: If not None, the subprocess's current directory will be changed to
      |cwd| before it's executed.

  Returns:
    Return code from the command execution.
  """
  if not quiet:
    logging.debug(' '.join(args) + ' ' + (cwd or ''))
  with open(os.devnull, 'w') as devnull:
    p = subprocess.Popen(args=args, cwd=cwd, stdout=devnull,
                         stderr=devnull, stdin=devnull, shell=False)
    return p.wait()

def GetAllCmdOutput(args, cwd=None, quiet=False):
  """Open a subprocess to execute a program and returns its output.

  Args:
    args: A string or a sequence of program arguments. The program to execute is
      the string or the first item in the args sequence.
    cwd: If not None, the subprocess's current directory will be changed to
      |cwd| before it's executed.

  Returns:
    Captures and returns the command's stdout.
    Prints the command's stderr to logger (which defaults to stdout).
  """
  if not quiet:
    logging.debug(' '.join(args) + ' ' + (cwd or ''))
  with open(os.devnull, 'w') as devnull:
    p = subprocess.Popen(args=args, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=devnull, shell=False)
    stdout, stderr = p.communicate()
    if not quiet:
      logging.debug(' > stdout=[%s], stderr=[%s]', stdout, stderr)
    return stdout, stderr

class DeviceSideProcess(object):
  def __init__(self,
               cri,
               device_side_args,
               prevent_output=True,
               extra_ssh_args=None,
               leave_ssh_alive=False,
               env=None,
               login_shell=False):

    # Init members first so that Close will always succeed.
    self._cri = cri
    self._proc = None
    self._devnull = open(os.devnull, 'w')

    if prevent_output:
      out = self._devnull
    else:
      out = sys.stderr

    cri.RmRF('/tmp/cros_interface_remote_device_pid')
    cmd_str = ' '.join(device_side_args)
    if env:
      env_str = ' '.join(['%s=%s' % (k, v) for k, v in env.items()])
      cmd = env_str + ' ' + cmd_str
    else:
      cmd = cmd_str
    contents = """%s&\n""" % cmd
    contents += 'echo $! > /tmp/cros_interface_remote_device_pid\n'
    cri.PushContents(contents, '/tmp/cros_interface_remote_device_bootstrap.sh')

    cmdline = ['/bin/bash']
    if login_shell:
      cmdline.append('-l')
    cmdline.append('/tmp/cros_interface_remote_device_bootstrap.sh')
    proc = subprocess.Popen(
      cri.FormSSHCommandLine(cmdline,
                              extra_ssh_args=extra_ssh_args),
      stdout=out,
      stderr=out,
      stdin=self._devnull,
      shell=False)

    time.sleep(0.1)
    def TryGetResult():
      try:
        self._pid = cri.GetFileContents(
            '/tmp/cros_interface_remote_device_pid').strip()
        return True
      except OSError:
        return False
    try:
      util.WaitFor(TryGetResult, 5)
    except util.TimeoutException:
      raise Exception('Something horrible has happened!')

    # Killing the ssh session leaves the process running. We dont
    # need it anymore, unless we have port-forwards.
    if not leave_ssh_alive:
      proc.kill()
    else:
      self._proc = proc

    self._pid = int(self._pid)
    if not self.IsAlive():
      raise OSError('Process did not come up or did not stay alive very long!')
    self._cri = cri

  def Close(self, try_sigint_first=False):
    if self.IsAlive():
      # Try to politely shutdown, first.
      if try_sigint_first:
        logging.debug("kill -INT %i" % self._pid)
        self._cri.GetAllCmdOutput(
          ['kill', '-INT', str(self._pid)], quiet=True)
        try:
          self.Wait(timeout=0.5)
        except util.TimeoutException:
          pass

      if self.IsAlive():
        logging.debug("kill -KILL %i" % self._pid)
        self._cri.GetAllCmdOutput(
          ['kill', '-KILL', str(self._pid)], quiet=True)
        try:
          self.Wait(timeout=5)
        except util.TimeoutException:
          pass

      if self.IsAlive():
        raise Exception('Could not shutdown the process.')

    self._cri = None
    if self._proc:
      self._proc.kill()
      self._proc = None

    if self._devnull:
      self._devnull.close()
      self._devnull = None

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.Close()
    return

  def Wait(self, timeout=1):
    if not self._pid:
      raise Exception('Closed')
    def IsDone():
      return not self.IsAlive()
    util.WaitFor(IsDone, timeout)
    self._pid = None

  def IsAlive(self, quiet=True):
    if not self._pid:
      return False
    exists = self._cri.FileExistsOnDevice('/proc/%i/cmdline' % self._pid,
                                          quiet=quiet)
    return exists

def HasSSH():
  try:
    RunCmd(['ssh'], quiet=True)
    RunCmd(['scp'], quiet=True)
    logging.debug("HasSSH()->True")
    return True
  except OSError:
    logging.debug("HasSSH()->False")
    return False

class LoginException(Exception):
  pass

class KeylessLoginRequiredException(LoginException):
  pass

class CrOSInterface(object):
  # pylint: disable=R0923
  def __init__(self, hostname, ssh_identity = None):
    self._hostname = hostname
    self._ssh_identity = None
    self._hostfile = tempfile.NamedTemporaryFile()
    self._hostfile.flush()
    self._ssh_args = ['-o ConnectTimeout=5',
                      '-o StrictHostKeyChecking=no',
                      '-o KbdInteractiveAuthentication=no',
                      '-o PreferredAuthentications=publickey',
                      '-o UserKnownHostsFile=%s' % self._hostfile.name]

    # List of ports generated from GetRemotePort() that may not be in use yet.
    self._reserved_ports = []

    if ssh_identity:
      self._ssh_identity = os.path.abspath(os.path.expanduser(ssh_identity))

  @property
  def hostname(self):
    return self._hostname

  def FormSSHCommandLine(self, args, extra_ssh_args=None):
    full_args = ['ssh',
                 '-o ForwardX11=no',
                 '-o ForwardX11Trusted=no',
                 '-n'] + self._ssh_args
    if self._ssh_identity is not None:
      full_args.extend(['-i', self._ssh_identity])
    if extra_ssh_args:
      full_args.extend(extra_ssh_args)
    full_args.append('root@%s' % self._hostname)
    full_args.extend(args)
    return full_args

  def GetAllCmdOutput(self, args, cwd=None, quiet=False):
    return GetAllCmdOutput(self.FormSSHCommandLine(args), cwd, quiet=quiet)

  def _RemoveSSHWarnings(self, toClean):
    """Removes specific ssh warning lines from a string.

    Args:
      toClean: A string that may be containing multiple lines.

    Returns:
      A copy of toClean with all the Warning lines removed.
    """
    # Remove the Warning about connecting to a new host for the first time.
    return re.sub('Warning: Permanently added [^\n]* to the list of known '
                  'hosts.\s\n', '', toClean)

  def TryLogin(self):
    logging.debug('TryLogin()')
    stdout, stderr = self.GetAllCmdOutput(['echo', '$USER'], quiet=True)

    # The initial login will add the host to the hosts file but will also print
    # a warning to stderr that we need to remove.
    stderr = self._RemoveSSHWarnings(stderr)
    if stderr != '':
      if 'Host key verification failed' in stderr:
        raise LoginException(('%s host key verification failed. ' +
                             'SSH to it manually to fix connectivity.') %
            self._hostname)
      if 'Operation timed out' in stderr:
        raise LoginException('Timed out while logging into %s' % self._hostname)
      if 'UNPROTECTED PRIVATE KEY FILE!' in stderr:
        raise LoginException('Permissions for %s are too open. To fix this,\n'
                             'chmod 600 %s' % (self._ssh_identity,
                                               self._ssh_identity))
      if 'Permission denied (publickey,keyboard-interactive)' in stderr:
        raise KeylessLoginRequiredException(
          'Need to set up ssh auth for %s' % self._hostname)
      raise LoginException('While logging into %s, got %s' % (
          self._hostname, stderr))
    if stdout != 'root\n':
      raise LoginException(
        'Logged into %s, expected $USER=root, but got %s.' % (
          self._hostname, stdout))

  def FileExistsOnDevice(self, file_name, quiet=False):
    stdout, stderr = self.GetAllCmdOutput([
        'if', 'test', '-a', file_name, ';',
        'then', 'echo', '1', ';',
        'fi'
        ], quiet=True)
    if stderr != '':
      if "Connection timed out" in stderr:
        raise OSError('Machine wasn\'t responding to ssh: %s' %
                      stderr)
      raise OSError('Unepected error: %s' % stderr)
    exists = stdout == '1\n'
    if not quiet:
      logging.debug("FileExistsOnDevice(<text>, %s)->%s" % (
          file_name, exists))
    return exists

  def PushFile(self, filename, remote_filename):
    args = ['scp', '-r' ] + self._ssh_args
    if self._ssh_identity:
      args.extend(['-i', self._ssh_identity])

    args.extend([os.path.abspath(filename),
                 'root@%s:%s' % (self._hostname, remote_filename)])

    stdout, stderr = GetAllCmdOutput(args, quiet=True)
    if stderr != '':
      assert 'No such file or directory' in stderr
      raise OSError

  def PushContents(self, text, remote_filename):
    logging.debug("PushContents(<text>, %s)" % remote_filename)
    with tempfile.NamedTemporaryFile() as f:
      f.write(text)
      f.flush()
      self.PushFile(f.name, remote_filename)

  def GetFileContents(self, filename):
    with tempfile.NamedTemporaryFile() as f:
      args = ['scp'] + self._ssh_args
      if self._ssh_identity:
        args.extend(['-i', self._ssh_identity])

      args.extend(['root@%s:%s' % (self._hostname, filename),
                   os.path.abspath(f.name)])

      stdout, stderr = GetAllCmdOutput(args, quiet=True)

      if stderr != '':
        assert 'No such file or directory' in stderr
        raise OSError

      with open(f.name, 'r') as f2:
        res = f2.read()
        logging.debug("GetFileContents(%s)->%s" % (filename, res))
        return res

  def ListProcesses(self):
    stdout, stderr = self.GetAllCmdOutput([
        '/bin/ps', '--no-headers',
        '-A',
        '-o', 'pid,args'], quiet=True)
    assert stderr == ''
    procs = []
    for l in stdout.split('\n'): # pylint: disable=E1103
      if l == '':
        continue
      m = re.match('^\s*(\d+)\s+(.+)', l, re.DOTALL)
      assert m
      procs.append(m.groups())
    logging.debug("ListProcesses(<predicate>)->[%i processes]" % len(procs))
    return procs

  def RmRF(self, filename):
    logging.debug("rm -rf %s" % filename)
    self.GetCmdOutput(['rm', '-rf', filename], quiet=True)

  def KillAllMatching(self, predicate):
    kills = ['kill', '-KILL']
    for p in self.ListProcesses():
      if predicate(p[1]):
        logging.info('Killing %s', repr(p))
        kills.append(p[0])
    logging.debug("KillAllMatching(<predicate>)->%i" % (len(kills) - 2))
    if len(kills) > 2:
      self.GetCmdOutput(kills, quiet=True)
    return len(kills) - 2

  def IsServiceRunning(self, service_name):
    stdout, stderr = self.GetAllCmdOutput([
        'status', service_name], quiet=True)
    assert stderr == ''
    running = 'running, process' in stdout
    logging.debug("IsServiceRunning(%s)->%s" % (service_name, running))
    return running

  def GetCmdOutput(self, args, quiet=False):
    stdout, stderr = self.GetAllCmdOutput(args, quiet=True)
    assert stderr == '', stderr
    if not quiet:
      logging.debug("GetCmdOutput(%s)->%s" % (repr(args), stdout))
    return stdout

  def GetRemotePort(self):
    netstat = self.GetAllCmdOutput(['netstat', '-ant'])
    netstat = netstat[0].split('\n')
    ports_in_use = []

    for line in netstat[2:]:
      if not line:
        continue
      address_in_use = line.split()[3]
      port_in_use = address_in_use.split(':')[-1]
      ports_in_use.append(int(port_in_use))

    ports_in_use.extend(self._reserved_ports)

    new_port = sorted(ports_in_use)[-1] + 1
    self._reserved_ports.append(new_port)

    return new_port

  def IsHTTPServerRunningOnPort(self, port):
    wget_output = self.GetAllCmdOutput(
        ['wget', 'localhost:%i' % (port), '-T1', '-t1'])

    if 'Connection refused' in wget_output[1]:
      return False

    return True
