# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

LOCK_EX = None  # Exclusive lock
LOCK_SH = None  # Shared lock
LOCK_NB = None  # Non-blocking (LockException is raised if resource is locked)


class LockException(Exception):
  pass


if os.name == 'nt':
  import win32con    # pylint: disable=import-error
  import win32file   # pylint: disable=import-error
  import pywintypes  # pylint: disable=import-error
  LOCK_EX = win32con.LOCKFILE_EXCLUSIVE_LOCK
  LOCK_SH = 0  # the default
  LOCK_NB = win32con.LOCKFILE_FAIL_IMMEDIATELY
  _OVERLAPPED = pywintypes.OVERLAPPED()
elif os.name == 'posix':
  import fcntl       # pylint: disable=import-error
  LOCK_EX = fcntl.LOCK_EX
  LOCK_SH = fcntl.LOCK_SH
  LOCK_NB = fcntl.LOCK_NB


def LockFile(target_file, flags):
  """ Lock the target file. Note that if |target_file| is closed, the lock is
    automatically released.
  Args:
    target_file: file handle of the file to acquire lock.
    flags: can be any of the type LOCK_EX, LOCK_SH, LOCK_NB, or a bitwise
      OR combination of flags.
  """
  assert flags in (
      LOCK_EX, LOCK_SH, LOCK_NB, LOCK_EX | LOCK_NB, LOCK_SH | LOCK_NB)
  if os.name == 'nt':
    _LockImplWin(target_file, flags)
  elif os.name == 'posix':
    _LockImplPosix(target_file, flags)
  else:
    raise NotImplementedError('%s is not supported' % os.name)


def UnlockFile(target_file):
  """ Unlock the target file.
  Args:
    target_file: file handle of the file to release the lock.
  """
  if os.name == 'nt':
    _UnlockImplWin(target_file)
  elif os.name == 'posix':
    _UnlockImplPosix(target_file)
  else:
    raise NotImplementedError('%s is not supported' % os.name)

# These implementations are based on
# http://code.activestate.com/recipes/65203/

def _LockImplWin(target_file, flags):
  hfile = win32file._get_osfhandle(target_file.fileno())
  try:
    win32file.LockFileEx(hfile, flags, 0, -0x10000, _OVERLAPPED)
  except pywintypes.error, exc_value:
    if exc_value[0] == 33:
      raise LockException('Error trying acquiring lock of %s: %s' %
                          (target_file.name, exc_value[2]))
    else:
      raise


def _UnlockImplWin(target_file):
  hfile = win32file._get_osfhandle(target_file.fileno())
  try:
    win32file.UnlockFileEx(hfile, 0, -0x10000, _OVERLAPPED)
  except pywintypes.error, exc_value:
    if exc_value[0] == 158:
      # error: (158, 'UnlockFileEx', 'The segment is already unlocked.')
      # To match the 'posix' implementation, silently ignore this error
      pass
    else:
      # Q:  Are there exceptions/codes we should be dealing with here?
      raise


def _LockImplPosix(target_file, flags):
  try:
    fcntl.flock(target_file.fileno(), flags)
  except IOError, exc_value:
    if exc_value[0] == 11 or exc_value[0] == 35:
      raise LockException('Error trying acquiring lock of %s: %s' %
                          (target_file.name, exc_value[1]))
    else:
      raise


def _UnlockImplPosix(target_file):
  fcntl.flock(target_file.fileno(), fcntl.LOCK_UN)
