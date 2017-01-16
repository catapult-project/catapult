# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import posixpath

from devil.android import device_errors

logger = logging.getLogger(__name__)


_CMDLINE_DIR = '/data/local/tmp'
_CMDLINE_DIR_LEGACY = '/data/local'


class FlagChanger(object):
  """Changes the flags Chrome runs with.

    Flags can be temporarily set for a particular set of unit tests.  These
    tests should call Restore() to revert the flags to their original state
    once the tests have completed.
  """

  def __init__(self, device, cmdline_file):
    """Initializes the FlagChanger and records the original arguments.

    Args:
      device: A DeviceUtils instance.
      cmdline_file: Name of the command line file where to store flags.
    """
    self._device = device

    unused_dir, basename = posixpath.split(cmdline_file)
    self._cmdline_path = posixpath.join(_CMDLINE_DIR, basename)

    # TODO(catapult:#3112): Make this fail instead of warn after all clients
    # have been switched.
    if unused_dir:
      logging.warning(
          'cmdline_file argument of %s() should be a file name only (not a'
          ' full path).', type(self))
      if cmdline_file != self._cmdline_path:
        logging.warning(
            'Client supplied %r, but %r will be used instead.',
            cmdline_file, self._cmdline_path)

    cmdline_path_legacy = posixpath.join(_CMDLINE_DIR_LEGACY, basename)
    if self._device.PathExists(cmdline_path_legacy):
      logging.warning(
            'Removing legacy command line file %r.', cmdline_path_legacy)
      self._device.RemovePath(cmdline_path_legacy, as_root=True)

    stored_flags = ''
    if self._device.PathExists(self._cmdline_path):
      try:
        stored_flags = self._device.ReadFile(self._cmdline_path).strip()
      except device_errors.CommandFailedError:
        pass
    # Store the flags as a set to facilitate adding and removing flags.
    self._state_stack = [set(self._TokenizeFlags(stored_flags))]

  def ReplaceFlags(self, flags):
    """Replaces the flags in the command line with the ones provided.
       Saves the current flags state on the stack, so a call to Restore will
       change the state back to the one preceeding the call to ReplaceFlags.

    Args:
      flags: A sequence of command line flags to set, eg. ['--single-process'].
             Note: this should include flags only, not the name of a command
             to run (ie. there is no need to start the sequence with 'chrome').
    """
    new_flags = set(flags)
    self._state_stack.append(new_flags)
    self._UpdateCommandLineFile()

  def AddFlags(self, flags):
    """Appends flags to the command line if they aren't already there.
       Saves the current flags state on the stack, so a call to Restore will
       change the state back to the one preceeding the call to AddFlags.

    Args:
      flags: A sequence of flags to add on, eg. ['--single-process'].
    """
    self.PushFlags(add=flags)

  def RemoveFlags(self, flags):
    """Removes flags from the command line, if they exist.
       Saves the current flags state on the stack, so a call to Restore will
       change the state back to the one preceeding the call to RemoveFlags.

       Note that calling RemoveFlags after AddFlags will result in having
       two nested states.

    Args:
      flags: A sequence of flags to remove, eg. ['--single-process'].  Note
             that we expect a complete match when removing flags; if you want
             to remove a switch with a value, you must use the exact string
             used to add it in the first place.
    """
    self.PushFlags(remove=flags)

  def PushFlags(self, add=None, remove=None):
    """Appends and removes flags to/from the command line if they aren't already
       there. Saves the current flags state on the stack, so a call to Restore
       will change the state back to the one preceeding the call to PushFlags.

    Args:
      add: A list of flags to add on, eg. ['--single-process'].
      remove: A list of flags to remove, eg. ['--single-process'].  Note that we
              expect a complete match when removing flags; if you want to remove
              a switch with a value, you must use the exact string used to add
              it in the first place.
    """
    new_flags = self._state_stack[-1].copy()
    if add:
      new_flags.update(add)
    if remove:
      new_flags.difference_update(remove)
    self.ReplaceFlags(new_flags)

  def Restore(self):
    """Restores the flags to their state prior to the last AddFlags or
       RemoveFlags call.
    """
    # The initial state must always remain on the stack.
    assert len(self._state_stack) > 1, (
      "Mismatch between calls to Add/RemoveFlags and Restore")
    self._state_stack.pop()
    self._UpdateCommandLineFile()

  def _UpdateCommandLineFile(self):
    """Writes out the command line to the file, or removes it if empty."""
    current_flags = list(self._state_stack[-1])
    logger.info('Current flags: %s', current_flags)
    # Root is not required to write to /data/local/tmp/.
    if current_flags:
      # The first command line argument doesn't matter as we are not actually
      # launching the chrome executable using this command line.
      cmd_line = ' '.join(['_'] + current_flags)
      self._device.WriteFile(
          self._cmdline_path, cmd_line)
      file_contents = self._device.ReadFile(
          self._cmdline_path).rstrip()
      assert file_contents == cmd_line, (
          'Failed to set the command line file at %s' % self._cmdline_path)
    else:
      self._device.RunShellCommand('rm ' + self._cmdline_path)
      assert not self._device.FileExists(self._cmdline_path), (
          'Failed to remove the command line file at %s' % self._cmdline_path)

  @staticmethod
  def _TokenizeFlags(line):
    """Changes the string containing the command line into a list of flags.

    Follows similar logic to CommandLine.java::tokenizeQuotedArguments:
    * Flags are split using whitespace, unless the whitespace is within a
      pair of quotation marks.
    * Unlike the Java version, we keep the quotation marks around switch
      values since we need them to re-create the file when new flags are
      appended.

    Args:
      line: A string containing the entire command line.  The first token is
            assumed to be the program name.
    """
    if not line:
      return []

    tokenized_flags = []
    current_flag = ""
    within_quotations = False

    # Move through the string character by character and build up each flag
    # along the way.
    for c in line.strip():
      if c is '"':
        if len(current_flag) > 0 and current_flag[-1] == '\\':
          # Last char was a backslash; pop it, and treat this " as a literal.
          current_flag = current_flag[0:-1] + '"'
        else:
          within_quotations = not within_quotations
          current_flag += c
      elif not within_quotations and (c is ' ' or c is '\t'):
        if current_flag is not "":
          tokenized_flags.append(current_flag)
          current_flag = ""
      else:
        current_flag += c

    # Tack on the last flag.
    if not current_flag:
      if within_quotations:
        logger.warn('Unterminated quoted argument: ' + line)
    else:
      tokenized_flags.append(current_flag)

    # Return everything but the program name.
    return tokenized_flags[1:]
