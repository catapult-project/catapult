# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import optparse
import sys
import shlex
import logging
import copy

from telemetry.core import browser_finder
from telemetry.core import wpr_modes

class BrowserOptions(optparse.Values):
  """Options to be used for discovering and launching a browser."""

  def __init__(self, browser_type=None):
    optparse.Values.__init__(self)

    self.browser_type = browser_type
    self.browser_executable = None
    self.chrome_root = None
    self.android_device = None
    self.cros_ssh_identity = None

    self.dont_override_profile = False
    self.extra_browser_args = []
    self.extra_wpr_args = []
    self.show_stdout = False
    self.extensions_to_load = []

    self.cros_remote = None
    self.wpr_mode = wpr_modes.WPR_OFF
    self.wpr_make_javascript_deterministic = True

    self.browser_user_agent_type = None

    self.trace_dir = None
    self.verbosity = 0

    self.page_filter = None
    self.page_filter_exclude = None

  def Copy(self):
    return copy.deepcopy(self)

  def CreateParser(self, *args, **kwargs):
    parser = optparse.OptionParser(*args, **kwargs)

    # Selection group
    group = optparse.OptionGroup(parser, 'Which browser to use')
    group.add_option('--browser',
        dest='browser_type',
        default=None,
        help='Browser type to run, '
             'in order of priority. Supported values: list,%s' %
             browser_finder.ALL_BROWSER_TYPES)
    group.add_option('--browser-executable',
        dest='browser_executable',
        help='The exact browser to run.')
    group.add_option('--chrome-root',
        dest='chrome_root',
        help='Where to look for chrome builds.'
             'Defaults to searching parent dirs by default.')
    group.add_option('--device',
        dest='android_device',
        help='The android device ID to use'
             'If not specified, only 0 or 1 connected devcies are supported.')
    group.add_option('--keep_test_server_ports', action='store_true',
        help='Indicates the test server ports must be '
             'kept. When this is run via a sharder '
             'the test server ports should be kept and '
             'should not be reset.')
    group.add_option(
        '--remote',
        dest='cros_remote',
        help='The IP address of a remote ChromeOS device to use.')
    group.add_option('--identity',
        dest='cros_ssh_identity',
        default=None,
        help='The identity file to use when ssh\'ing into the ChromeOS device')
    parser.add_option_group(group)

    # Browser options
    group = optparse.OptionGroup(parser, 'Browser options')
    group.add_option('--dont-override-profile', action='store_true',
        dest='dont_override_profile',
        help='Uses the regular user profile instead of a clean one')
    group.add_option('--extra-browser-args',
        dest='extra_browser_args_as_string',
        help='Additional arguments to pass to the browser when it starts')
    group.add_option('--extra-wpr-args',
        dest='extra_wpr_args_as_string',
        help=('Additional arguments to pass to Web Page Replay. '
              'See third_party/webpagereplay/replay.py for usage.'))
    group.add_option('--show-stdout',
        action='store_true',
        help='When possible, will display the stdout of the process')
    parser.add_option_group(group)

    # Page set options
    group = optparse.OptionGroup(parser, 'Page set options')
    group.add_option('--page-repeat', dest='page_repeat', default=1,
        help='Number of times to repeat each individual ' +
        'page in the pageset before proceeding.')
    group.add_option('--pageset-repeat', dest='pageset_repeat', default=1,
        help='Number of times to repeat the entire pageset ' +
        'before finishing.')
    group.add_option('--pageset-shuffle', action='store_true',
        dest='pageset_shuffle',
        help='Shuffle the order of pages within a pageset.')
    group.add_option('--pageset-shuffle-order-file',
        dest='pageset_shuffle_order_file', default=None,
        help='Filename of an output of a previously run test on the current ' +
        'pageset. The tests will run in the same order again, overriding ' +
        'what is specified by --page-repeat and --pageset-repeat.')
    parser.add_option_group(group)

    # Debugging options
    group = optparse.OptionGroup(parser, 'When things go wrong')
    group.add_option(
      '--trace-dir', dest='trace_dir', default=None,
      help='Record traces and store them in this directory.')
    group.add_option(
      '-v', '--verbose', action='count', dest='verbosity',
      help='Increase verbosity level (repeat as needed)')
    parser.add_option_group(group)

    # Platform options
    group = optparse.OptionGroup(parser, 'Platform options')
    group.add_option('--no-performance-mode', action='store_true',
        help='Some platforms run on "full performance mode" where the '
        'benchmark is executed at maximum CPU speed in order to minimize noise '
        '(specially important for dashboards / continuous builds). '
        'This option prevents Telemetry from tweaking such platform settings.')

    real_parse = parser.parse_args
    def ParseArgs(args=None):
      defaults = parser.get_default_values()
      for k, v in defaults.__dict__.items():
        if k in self.__dict__ and self.__dict__[k] != None:
          continue
        self.__dict__[k] = v
      ret = real_parse(args, self) # pylint: disable=E1121

      if self.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
      elif self.verbosity:
        logging.basicConfig(level=logging.INFO)
      else:
        logging.basicConfig(level=logging.WARNING)

      if self.browser_executable and not self.browser_type:
        self.browser_type = 'exact'
      if not self.browser_executable and not self.browser_type:
        sys.stderr.write('Must provide --browser=<type>. ' +
                         'Use --browser=list for valid options.\n')
        sys.exit(1)
      if self.browser_type == 'list':
        types = browser_finder.GetAllAvailableBrowserTypes(self)
        sys.stderr.write('Available browsers:\n')
        sys.stdout.write('  %s\n' % '\n  '.join(types))
        sys.exit(1)
      if self.extra_browser_args_as_string: # pylint: disable=E1101
        tmp = shlex.split(
          self.extra_browser_args_as_string) # pylint: disable=E1101
        self.extra_browser_args.extend(tmp)
        delattr(self, 'extra_browser_args_as_string')
      if self.extra_wpr_args_as_string: # pylint: disable=E1101
        tmp = shlex.split(
          self.extra_wpr_args_as_string) # pylint: disable=E1101
        self.extra_wpr_args.extend(tmp)
        delattr(self, 'extra_wpr_args_as_string')
      return ret
    parser.parse_args = ParseArgs
    return parser

  def AppendExtraBrowserArg(self, arg):
    if arg not in self.extra_browser_args:
      self.extra_browser_args.append(arg)
