# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A wrapper around ssh for common operations on a CrOS-based device"""
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

# Some developers' workflow includes running the Chrome process from
# /usr/local/... instead of the default location. We have to check for both
# paths in order to support this workflow.
_CHROME_PATHS = ['/opt/google/chrome/chrome ',
                '/usr/local/opt/google/chrome/chrome ']

def IsRunningOnCrosDevice():
  """Returns True if we're on a ChromeOS device."""
  lsb_release = '/etc/lsb-release'
  if sys.platform.startswith('linux') and os.path.exists(lsb_release):
    with open(lsb_release, 'r') as f:
      res = f.read()
      if res.count('CHROMEOS_RELEASE_NAME'):
        return True
  return False

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
                         stderr=subprocess.PIPE, stdin=devnull)
    stdout, stderr = p.communicate()
    if not quiet:
      logging.debug(' > stdout=[%s], stderr=[%s]', stdout, stderr)
    return stdout, stderr

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
  def __init__(self, hostname = None, ssh_identity = None):
    self._hostname = hostname
    # List of ports generated from GetRemotePort() that may not be in use yet.
    self._reserved_ports = []

    if self.local:
      return

    self._ssh_identity = None
    self._ssh_args = ['-o ConnectTimeout=5',
                      '-o StrictHostKeyChecking=no',
                      '-o KbdInteractiveAuthentication=no',
                      '-o PreferredAuthentications=publickey',
                      '-o UserKnownHostsFile=/dev/null',
                      '-o ControlMaster=no']

    if ssh_identity:
      self._ssh_identity = os.path.abspath(os.path.expanduser(ssh_identity))

    # Establish master SSH connection using ControlPersist.
    # Since only one test will be run on a remote host at a time,
    # the control socket filename can be telemetry@hostname.
    self._ssh_control_file = '/tmp/' + 'telemetry' + '@' + hostname
    with open(os.devnull, 'w') as devnull:
      subprocess.call(self.FormSSHCommandLine(['-M', '-o ControlPersist=yes']),
                       stdin=devnull, stdout=devnull, stderr=devnull)

  def __enter__(self):
    return self

  def __exit__(self, *args):
    self.CloseConnection()

  @property
  def local(self):
    return not self._hostname

  @property
  def hostname(self):
    return self._hostname

  def FormSSHCommandLine(self, args, extra_ssh_args=None):
    if self.local:
      # We run the command through the shell locally for consistency with
      # how commands are run through SSH (crbug.com/239161). This work
      # around will be unnecessary once we implement a persistent SSH
      # connection to run remote commands (crbug.com/239607).
      return ['sh', '-c', " ".join(args)]

    full_args = ['ssh',
                 '-o ForwardX11=no',
                 '-o ForwardX11Trusted=no',
                 '-n', '-S', self._ssh_control_file] + self._ssh_args
    if self._ssh_identity is not None:
      full_args.extend(['-i', self._ssh_identity])
    if extra_ssh_args:
      full_args.extend(extra_ssh_args)
    full_args.append('root@%s' % self._hostname)
    full_args.extend(args)
    return full_args

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

  def RunCmdOnDevice(self, args, cwd=None, quiet=False):
    stdout, stderr = GetAllCmdOutput(
        self.FormSSHCommandLine(args), cwd, quiet=quiet)
    # The initial login will add the host to the hosts file but will also print
    # a warning to stderr that we need to remove.
    stderr = self._RemoveSSHWarnings(stderr)
    return stdout, stderr

  def TryLogin(self):
    logging.debug('TryLogin()')
    assert not self.local
    stdout, stderr = self.RunCmdOnDevice(['echo', '$USER'], quiet=True)
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

  def FileExistsOnDevice(self, file_name):
    if self.local:
      return os.path.exists(file_name)

    stdout, stderr = self.RunCmdOnDevice([
        'if', 'test', '-e', file_name, ';',
        'then', 'echo', '1', ';',
        'fi'
        ], quiet=True)
    if stderr != '':
      if "Connection timed out" in stderr:
        raise OSError('Machine wasn\'t responding to ssh: %s' %
                      stderr)
      raise OSError('Unexpected error: %s' % stderr)
    exists = stdout == '1\n'
    logging.debug("FileExistsOnDevice(<text>, %s)->%s" % (file_name, exists))
    return exists

  def PushFile(self, filename, remote_filename):
    if self.local:
      args = ['cp', '-r', filename, remote_filename]
      stdout, stderr = GetAllCmdOutput(args, quiet=True)
      if stderr != '':
        raise OSError('No such file or directory %s' % stderr)
      return

    args = ['scp', '-r' ] + self._ssh_args
    if self._ssh_identity:
      args.extend(['-i', self._ssh_identity])

    args.extend([os.path.abspath(filename),
                 'root@%s:%s' % (self._hostname, remote_filename)])

    stdout, stderr = GetAllCmdOutput(args, quiet=True)
    stderr = self._RemoveSSHWarnings(stderr)
    if stderr != '':
      raise OSError('No such file or directory %s' % stderr)

  def PushContents(self, text, remote_filename):
    logging.debug("PushContents(<text>, %s)" % remote_filename)
    with tempfile.NamedTemporaryFile() as f:
      f.write(text)
      f.flush()
      self.PushFile(f.name, remote_filename)

  def GetFile(self, filename, destfile=None):
    """Copies a local file |filename| to |destfile| on the device.

    Args:
      filename: The name of the local source file.
      destfile: The name of the file to copy to, and if it is not specified
        then it is the basename of the source file.

    """
    logging.debug("GetFile(%s, %s)" % (filename, destfile))
    if self.local:
      if destfile is not None and destfile != filename:
        shutil.copyfile(filename, destfile)
      return

    if destfile is None:
      destfile = os.path.basename(filename)
    args = ['scp'] + self._ssh_args
    if self._ssh_identity:
      args.extend(['-i', self._ssh_identity])

    args.extend(['root@%s:%s' % (self._hostname, filename),
                 os.path.abspath(destfile)])
    stdout, stderr = GetAllCmdOutput(args, quiet=True)
    stderr = self._RemoveSSHWarnings(stderr)
    if stderr != '':
      raise OSError('No such file or directory %s' % stderr)

  def GetFileContents(self, filename):
    """Get the contents of a file on the device.

    Args:
      filename: The name of the file on the device.

    Returns:
      A string containing the contents of the file.
    """
    # TODO: handle the self.local case
    assert not self.local
    t = tempfile.NamedTemporaryFile()
    self.GetFile(filename, t.name)
    with open(t.name, 'r') as f2:
      res = f2.read()
      logging.debug("GetFileContents(%s)->%s" % (filename, res))
      f2.close()
      return res

  def ListProcesses(self):
    """Returns (pid, cmd, ppid, state) of all processes on the device."""
    stdout, stderr = self.RunCmdOnDevice([
        '/bin/ps', '--no-headers',
        '-A',
        '-o', 'pid,ppid,args:4096,state'], quiet=True)
    assert stderr == '', stderr
    procs = []
    for l in stdout.split('\n'): # pylint: disable=E1103
      if l == '':
        continue
      m = re.match('^\s*(\d+)\s+(\d+)\s+(.+)\s+(.+)', l, re.DOTALL)
      assert m
      procs.append((int(m.group(1)), m.group(3).rstrip(),
                    int(m.group(2)), m.group(4)))
    logging.debug("ListProcesses(<predicate>)->[%i processes]" % len(procs))
    return procs

  def _GetSessionManagerPid(self, procs):
    """Returns the pid of the session_manager process, given the list of
    processes."""
    for pid, process, _, _ in procs:
      argv = process.split()
      if argv and os.path.basename(argv[0]) == 'session_manager':
        return pid
    return None

  def GetChromeProcess(self):
    """Locates the the main chrome browser process.

    Chrome on cros is usually in /opt/google/chrome, but could be in
    /usr/local/ for developer workflows - debug chrome is too large to fit on
    rootfs.

    Chrome spawns multiple processes for renderers. pids wrap around after they
    are exhausted so looking for the smallest pid is not always correct. We
    locate the session_manager's pid, and look for the chrome process that's an
    immediate child. This is the main browser process.
    """
    procs = self.ListProcesses()
    session_manager_pid = self._GetSessionManagerPid(procs)
    if not session_manager_pid:
      return None

    # Find the chrome process that is the child of the session_manager.
    for pid, process, ppid, _ in procs:
      if ppid != session_manager_pid:
        continue
      for path in _CHROME_PATHS:
        if process.startswith(path):
          return {'pid': pid, 'path': path, 'args': process}
    return None

  def GetChromePid(self):
    """Returns pid of main chrome browser process."""
    result = self.GetChromeProcess()
    if result and 'pid' in result:
      return result['pid']
    return None

  def RmRF(self, filename):
    logging.debug("rm -rf %s" % filename)
    self.RunCmdOnDevice(['rm', '-rf', filename], quiet=True)

  def Chown(self, filename):
    self.RunCmdOnDevice(['chown', '-R', 'chronos:chronos', filename])

  def KillAllMatching(self, predicate):
    kills = ['kill', '-KILL']
    for pid, cmd, _, _ in self.ListProcesses():
      if predicate(cmd):
        logging.info('Killing %s, pid %d' % cmd, pid)
        kills.append(pid)
    logging.debug("KillAllMatching(<predicate>)->%i" % (len(kills) - 2))
    if len(kills) > 2:
      self.RunCmdOnDevice(kills, quiet=True)
    return len(kills) - 2

  def IsServiceRunning(self, service_name):
    stdout, stderr = self.RunCmdOnDevice([
        'status', service_name], quiet=True)
    assert stderr == '', stderr
    running = 'running, process' in stdout
    logging.debug("IsServiceRunning(%s)->%s" % (service_name, running))
    return running

  def GetRemotePort(self):
    netstat = self.RunCmdOnDevice(['netstat', '-ant'])
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
    wget_output = self.RunCmdOnDevice(
        ['wget', 'localhost:%i' % (port), '-T1', '-t1'])

    if 'Connection refused' in wget_output[1]:
      return False

    return True

  def FilesystemMountedAt(self, path):
    """Returns the filesystem mounted at |path|"""
    df_out, _ = self.RunCmdOnDevice(['/bin/df', path])
    df_ary = df_out.split('\n')
    # 3 lines for title, mount info, and empty line.
    if len(df_ary) == 3:
      line_ary = df_ary[1].split()
      if line_ary:
        return line_ary[0]
    return None

  def CryptohomePath(self, user):
    """Returns the cryptohome mount point for |user|."""
    stdout, stderr = self.RunCmdOnDevice(
        ['cryptohome-path', 'user', "'%s'" % user])
    if stderr != '':
      raise OSError('cryptohome-path failed: %s' % stderr)
    return stdout.rstrip()

  def IsCryptohomeMounted(self, username, is_guest):
    """Returns True iff |user|'s cryptohome is mounted."""
    profile_path = self.CryptohomePath(username)
    mount = self.FilesystemMountedAt(profile_path)
    mount_prefix = 'guestfs' if is_guest else '/home/.shadow/'
    return mount and mount.startswith(mount_prefix)

  def TakeScreenShot(self, screenshot_prefix):
    """Takes a screenshot, useful for debugging failures."""
    # TODO(achuith): Find a better location for screenshots. Cros autotests
    # upload everything in /var/log so use /var/log/screenshots for now.
    SCREENSHOT_DIR = '/var/log/screenshots/'
    SCREENSHOT_EXT = '.png'

    self.RunCmdOnDevice(['mkdir', '-p', SCREENSHOT_DIR])
    for i in xrange(25):
      screenshot_file = ('%s%s-%d%s' %
                         (SCREENSHOT_DIR, screenshot_prefix, i, SCREENSHOT_EXT))
      if not self.FileExistsOnDevice(screenshot_file):
        self.RunCmdOnDevice([
            'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority '
            '/usr/local/bin/import',
            '-window root',
            '-depth 8',
            screenshot_file])
        return
    logging.warning('screenshot directory full.')

  def RestartUI(self, clear_enterprise_policy):
    logging.info('(Re)starting the ui (logs the user out)')
    if clear_enterprise_policy:
      self.RunCmdOnDevice(['stop', 'ui'])
      self.RmRF('/var/lib/whitelist/*')
      self.RmRF('/home/chronos/Local\ State')

    if self.IsServiceRunning('ui'):
      self.RunCmdOnDevice(['restart', 'ui'])
    else:
      self.RunCmdOnDevice(['start', 'ui'])

  def CloseConnection(self):
    if not self.local:
      with open(os.devnull, 'w') as devnull:
        subprocess.call(self.FormSSHCommandLine(['-O', 'exit', self._hostname]),
                        stdout=devnull, stderr=devnull)
