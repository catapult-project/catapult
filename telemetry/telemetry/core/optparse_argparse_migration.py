# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Code to handle the optparse -> argparse migration.

Once all Telemetry and Telemetry-dependent code switches to using these wrappers
instead of directly using optparse, incremental changes can be made to move the
underlying implementation from optparse to argparse before finally switching
directly to argparse.
"""

import argparse


def _AddArgumentImpl(parser, *args, **kwargs):
  if 'help' in kwargs:
    help_str = kwargs['help']
    help_str = help_str.replace('%default', '%(default)s')
    kwargs['help'] = help_str

  # optparse supported string values for the type argument, but argparse does
  # not, so convert here.
  if 'type' in kwargs:
    type_value = kwargs['type']
    if type_value == 'int':
      type_value = int
    elif type_value in ('string', 'str'):
      type_value = str
    elif type_value == 'float':
      type_value = float
    kwargs['type'] = type_value

  parser.add_argument(*args, **kwargs)


class ArgumentParser(argparse.ArgumentParser):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # parse_args behavior differs between optparse and argparse, so store a
    # reference to the original implementation now before we override it later.
    self.argparse_parse_args = self.parse_args

  def parse_args(self, args=None, namespace=None):
    """optparse-like override of argparse's parse_args."""
    # optparse's parse_args only parses flags that start with -- or -.
    # Positional args are returned as-is as a list of strings. For now, assert
    # that we're using this wrapper like optparse (no positional arguments
    # defined) and ensure that unknown args are all positional arguments.
    # All uses of positional args will have to be updated at the same time this
    # overridden parse_args is removed.
    for action in self._actions:
      if not action.option_strings:
        self.error('Tried to parse a defined positional argument. This is not '
                   'supported until former uses of optparse are migrated to '
                   'argparse')
    known_args, unknown_args = self.parse_known_args(args, namespace)
    for unknown in unknown_args:
      if unknown.startswith('-'):
        self.error(f'no such option: {unknown}')
    return known_args, unknown_args

  def add_option(self, *args, **kwargs):
    _AddArgumentImpl(self, *args, **kwargs)

  def add_option_group(self, *args, **kwargs):
    # We no-op since argparse's add_argument_group already associates the group
    # with the argument parser.
    pass

  def get_default_values(self):
    defaults = {}
    for action in self._actions:
      # In the event that multiple actions point to the same destination such
      # as --foo/--no-foo, use the default of the first defined one. This
      # appears to be consistent with how optparse did it.
      defaults.setdefault(action.dest, action.default)
    for k, v in self._defaults.items():
      if k in defaults:
        # This should never be hit since argparse sets the action's default if
        # it exists.
        assert defaults[k] == v
      defaults[k] = v
    return ArgumentValues(**defaults)

  @property
  def option_list(self):
    return self._actions

  @property
  def defaults(self):
    return self._defaults


class _ArgumentGroup(argparse._ArgumentGroup):

  def add_option(self, *args, **kwargs):
    _AddArgumentImpl(self, *args, **kwargs)

  @property
  def option_list(self):
    return self._actions


# Used by BrowserFinderOptions
class ArgumentValues(argparse.Namespace):
  # To be filled in over time.
  def ensure_value(self, attr, value):
    if not hasattr(self, attr) or getattr(self, attr) is None:
      setattr(self, attr, value)
    return getattr(self, attr)


def CreateOptionGroup(parser, title, description=None):
  """Creates an ArgumentParser group using the same arguments as optparse.

  See Python's optparse.OptionGroup documentation for argument descriptions.
  """
  # Copied from argparse's source code for add_argument_group, but using our own
  # class.
  group = _ArgumentGroup(parser, title, description)
  parser._action_groups.append(group)
  return group


def CreateFromOptparseInputs(usage=None, description=None):
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
  usage = usage or '%prog [options]'
  usage = usage.replace('%prog', '%(prog)s')
  return ArgumentParser(usage=usage, description=description)
