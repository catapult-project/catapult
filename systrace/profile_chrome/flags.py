# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse

def SystraceOptions(parser):
  systrace_opts = optparse.OptionGroup(parser, 'Systrace tracing options')
  systrace_opts.add_option('-s', '--systrace', help='Capture a systrace with '
                           'the chosen comma-delimited systrace categories. You'
                           ' can also capture a combined Chrome + systrace by '
                           'enabling both types of categories. Use "list" to '
                           'see the available categories. Systrace is disabled '
                           'by default.', metavar='SYS_CATEGORIES',
                           dest='systrace_categories', default='')
  return systrace_opts


def OutputOptions(parser):
  output_options = optparse.OptionGroup(parser, 'Output options')
  output_options.add_option('-o', '--output', help='Save trace output to file.')
  output_options.add_option('--json', help='Save trace as raw JSON instead of '
                            'HTML.', action='store_true')
  output_options.add_option('--view', help='Open resulting trace file in a '
                            'browser.', action='store_true')
  return output_options
