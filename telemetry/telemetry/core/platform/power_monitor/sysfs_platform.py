# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class SysfsPlatform(object):
  """A platform-specific utility class for running shell commands and properly
  gathering c-state data.
  """
  def RunShellCommand(self, command):
    """Run command on this particular shell.

    Args:
        A command string to be executed in the shell.

    Returns:
        A string containing the results of the command.
    """
    raise NotImplementedError()

  @staticmethod
  def ParseStateSample(sample, time):
    """Parse a single c-state residency sample.

    Args:
        sample: A sample of c-state residency times to be parsed. Organized as
            a dictionary mapping CPU name to a string containing all c-state
            names, the times in each state, and the latency of each state all
            separated by newlines.
        time: The epoch time at which the sample was taken.

    Returns:
        Dictionary associating a c-state with a time.
    """
    raise NotImplementedError()
