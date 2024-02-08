# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Code to handle the optparse -> argparse migration.

Once all Telemetry and Telemetry-dependent code switches to using these wrappers
instead of directly using optparse, incremental changes can be made to move the
underlying implementation from optparse to argparse before finally switching
directly to argparse.
"""

import optparse  # pylint:disable=deprecated-module

class ArgumentParser(optparse.OptionParser):
  # To be filled in over time.
  pass


class ArgumentValues(optparse.Values):
  # To be filled in over time.
  pass


def CreateOptionGroup(parser, title, description=None):
  """Creates an ArgumentParser group using the same arguments as optparse.

  See Python's optparse.OptionGroup documentation for argument descriptions.
  """
  return optparse.OptionGroup(parser, title, description=description)


def CreateFromOptparseInputs(
    usage='%%prog [options]',
    description=None):
  """Creates an ArgumentParser using the same constructor arguments as optparse.

  See Python's optparse.OptionParser documentation for argument descriptions.
  The following args have been omitted since they do not appear to be used in
  Telemetry, but can be added later if necessary.
    * option_list
    * option_class
    * version
    * conflict_handler
    * formatter
    * add_help_option
    * prog
    * epilog
  """
  return ArgumentParser(usage=usage, description=description)
