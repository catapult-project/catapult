# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse


class RepeatOptions(object):
  def __init__(self, page_repeat=None, pageset_repeat=None):
    self.page_repeat = page_repeat
    self.pageset_repeat = pageset_repeat

  def __deepcopy__(self, _):
    return RepeatOptions(self.page_repeat, self.pageset_repeat)

  @classmethod
  def AddCommandLineArgs(cls, parser):
    group = optparse.OptionGroup(parser, 'Repeat options')
    group.add_option('--page-repeat', default=1, type='int',
                     help='Number of times to repeat each individual page '
                     'before proceeding with the next page in the pageset.')
    group.add_option('--pageset-repeat', default=1, type='int',
                     help='Number of times to repeat the entire pageset.')

  def UpdateFromParseResults(self, finder_options):
    """Copies options from the given options object to this object."""
    self.page_repeat = finder_options.page_repeat
    self.pageset_repeat = finder_options.pageset_repeat

  def IsRepeating(self):
    """Returns True if we will be repeating pages or pagesets."""
    return self.page_repeat != 1 or self.pageset_repeat != 1
