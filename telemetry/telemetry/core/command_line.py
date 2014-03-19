# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse

from telemetry.core import camel_case


class ArgumentHandlerMixIn(object):
  """A structured way to handle command-line arguments.

  In AddCommandLineArgs, add command-line arguments.
  In ProcessCommandLineArgs, validate them and store them in a private class
  variable. This way, each class encapsulates its own arguments, without needing
  to pass an arguments object around everywhere.
  """

  @classmethod
  def AddCommandLineArgs(cls, parser):
    """Override to accept custom command-line arguments."""

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    """Override to process command-line arguments.

    We pass in parser so we can call parser.error()."""


class Command(ArgumentHandlerMixIn):
  """Represents a command-line sub-command for use with an argparse sub-parser.

  E.g. "svn checkout", "svn update", and "svn commit" are separate sub-commands.

  Example usage, to set up argparse to use these commands:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    for command in COMMANDS:
      subparser = subparsers.add_parser(
          command.Name(), help=command.Description())
      subparser.set_defaults(command=command)
      command.AddCommandLineArgs(subparser)

    args = parser.parse_args()
    args.command.ProcessCommandLineArgs(parser, args)
    args.command().Run(args)
  """

  @classmethod
  def Name(cls):
    return camel_case.ToUnderscore(cls.__name__)

  @classmethod
  def Description(cls):
    if cls.__doc__:
      return cls.__doc__.splitlines()[0]
    else:
      return ''

  def Run(self, args):
    raise NotImplementedError()


# TODO: Convert everything to argparse.
class OptparseCommand(Command):
  usage = ''

  @classmethod
  def CreateParser(cls):
    return optparse.OptionParser('%%prog %s %s' % (cls.Name(), cls.usage))

  def Run(self, args):
    raise NotImplementedError()
