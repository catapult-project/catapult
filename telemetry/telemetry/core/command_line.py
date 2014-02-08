# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse


class Command(object):
  @property
  def name(self):
    return self.__class__.__name__.lower()

  @property
  def description(self):
    return self.__doc__

  def AddCommandLineOptions(self, parser):
    pass


class ArgparseCommand(Command):
  def ProcessCommandLine(self, parser, args):
    pass

  def Run(self, args):
    raise NotImplementedError()


# TODO: Convert everything to argparse.
class OptparseCommand(Command):
  usage = ''

  def CreateParser(self):
    return optparse.OptionParser('%%prog %s %s' % (self.name, self.usage))

  def ProcessCommandLine(self, parser, options, args):
    pass

  def Run(self, options, args):
    raise NotImplementedError()
