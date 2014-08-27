# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import distutils.spawn
import logging
import os
import re
import stat
import subprocess

from telemetry.core.platform import desktop_platform_backend
from telemetry.core.platform import ps_util


class PosixPlatformBackend(desktop_platform_backend.DesktopPlatformBackend):

  # This is an abstract class. It is OK to have abstract methods.
  # pylint: disable=W0223

  def RunCommand(self, args):
    return subprocess.Popen(args, stdout=subprocess.PIPE).communicate()[0]

  def GetFileContents(self, path):
    with open(path, 'r') as f:
      return f.read()

  def GetPsOutput(self, columns, pid=None):
    """Returns output of the 'ps' command as a list of lines.
    Subclass should override this function.

    Args:
      columns: A list of require columns, e.g., ['pid', 'pss'].
      pid: If not None, returns only the information of the process
         with the pid.
    """
    args = ['ps']
    args.extend(['-p', str(pid)] if pid != None else ['-e'])
    for c in columns:
      args.extend(['-o', c + '='])
    return self.RunCommand(args).splitlines()

  def _GetTopOutput(self, pid, columns):
    """Returns output of the 'top' command as a list of lines.

    Args:
      pid: pid of process to examine.
      columns: A list of require columns, e.g., ['idlew', 'vsize'].
    """
    args = ['top']
    args.extend(['-pid', str(pid), '-l', '1', '-s', '0', '-stats',
        ','.join(columns)])
    return self.RunCommand(args).splitlines()

  def GetChildPids(self, pid):
    """Returns a list of child pids of |pid|."""
    ps_output = self.GetPsOutput(['pid', 'ppid', 'state'])
    ps_line_re = re.compile(
        '\s*(?P<pid>\d+)\s*(?P<ppid>\d+)\s*(?P<state>\S*)\s*')
    processes = []
    for pid_ppid_state in ps_output:
      m = ps_line_re.match(pid_ppid_state)
      assert m, 'Did not understand ps output: %s' % pid_ppid_state
      processes.append((m.group('pid'), m.group('ppid'), m.group('state')))
    return ps_util.GetChildPids(processes, pid)

  def GetCommandLine(self, pid):
    command = self.GetPsOutput(['command'], pid)
    return command[0] if command else None

  def CanLaunchApplication(self, application):
    return bool(distutils.spawn.find_executable(application))

  def IsApplicationRunning(self, application):
    ps_output = self.GetPsOutput(['command'])
    application_re = re.compile(
        '(.*%s|^)%s(\s|$)' % (os.path.sep, application))
    return any(application_re.match(cmd) for cmd in ps_output)

  def LaunchApplication(
      self, application, parameters=None, elevate_privilege=False):
    assert application, 'Must specify application to launch'

    if os.path.sep not in application:
      application = distutils.spawn.find_executable(application)
      assert application, 'Failed to find application in path'

    args = [application]

    if parameters:
      assert isinstance(parameters, list), 'parameters must be a list'
      args += parameters

    def IsSetUID(path):
      return (os.stat(path).st_mode & stat.S_ISUID) == stat.S_ISUID

    def IsElevated():
      p = subprocess.Popen(
          ['sudo', '-nv'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
           stderr=subprocess.STDOUT)
      stdout = p.communicate()[0]
      # Some versions of sudo set the returncode based on whether sudo requires
      # a password currently. Other versions return output when password is
      # required and no output when the user is already authenticated.
      return not p.returncode and not stdout

    if elevate_privilege and not IsSetUID(application):
      args = ['sudo'] + args
      if not IsElevated():
        print ('Telemetry needs to run %s under sudo. Please authenticate.' %
               application)
        subprocess.check_call(['sudo', '-v'])  # Synchronously authenticate.

        prompt = ('Would you like to always allow %s to be run as the current '
                  'user without sudo? If so, Telemetry will '
                  '`sudo chmod +s %s`. (y/N)' % (application, application))
        if raw_input(prompt).lower() == 'y':
          subprocess.check_call(['sudo', 'chmod', '+s', application])

    stderror_destination = subprocess.PIPE
    if logging.getLogger().isEnabledFor(logging.DEBUG):
      stderror_destination = None

    return subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=stderror_destination)
