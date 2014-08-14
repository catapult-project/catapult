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
  def ParseStateSample(sample):
    """Parse a single c-state residency sample.

    Args:
        sample: A sample of c-state residency times to be parsed. Organized as
            a dictionary mapping CPU name to a string containing all c-state
            names, the times in each state, the latency of each state, and the
            time at which the sample was taken all separated by newlines.
            Ex: {'cpu0': 'C0\nC1\n5000\n2000\n20\n30\n1406673171'}

    Returns:
        Dictionary associating a c-state with a time.
    """
    raise NotImplementedError()
