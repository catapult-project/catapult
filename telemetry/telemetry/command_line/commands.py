# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines the commands provided by Telemetry: Run, List."""

import json
import logging
import optparse
import os
import sys

from telemetry import benchmark
from telemetry.internal.browser import browser_finder
from telemetry.internal.browser import browser_options
from telemetry.internal.util import command_line
from telemetry.util import matching


def _SetExpectations(bench, path):
  if path and os.path.exists(path):
    with open(path) as fp:
      bench.AugmentExpectationsWithFile(fp.read())
  return bench.expectations


def _IsBenchmarkEnabled(bench, possible_browser, expectations_file):
  b = bench()
  expectations = _SetExpectations(b, expectations_file)
  expectations.SetTags(possible_browser.GetTypExpectationsTags())
  return (
      # Test that the current platform is supported.
      any(t.ShouldDisable(possible_browser.platform, possible_browser)
          for t in b.SUPPORTED_PLATFORMS) and
      # Test that expectations say it is enabled.
      not expectations.IsBenchmarkDisabled(possible_browser.platform,
                                           possible_browser))


def _GetStoriesWithTags(b):
  """Finds all stories and their tags given a benchmark.

  Args:
    b: a subclass of benchmark.Benchmark
  Returns:
    A list of dicts for the stories, each of the form:
    {
      'name' : story.name
      'tags': list(story.tags)
    }
  """
  # Create a options object which hold default values that are expected
  # by Benchmark.CreateStoriesWithTags(options) method.
  parser = optparse.OptionParser()
  b.AddBenchmarkCommandLineArgs(parser)
  options, _ = parser.parse_args([])

  # Some benchmarks require special options, such as *.cluster_telemetry.
  # Just ignore them for now.
  try:
    story_set = b().CreateStorySet(options)
  # pylint: disable=broad-except
  except Exception as e:
    logging.warning('Unable to get stories for %s due to "%s"', b.Name(), e)
    story_set = []

  stories_info = []
  for s in story_set:
    stories_info.append({
        'name': s.name,
        'tags': list(s.tags)
    })
  return sorted(stories_info)


def PrintBenchmarkList(
    benchmarks, possible_browser, expectations_file, output_pipe=None,
    json_pipe=None):
  """ Print benchmarks that are not filtered in the same order of benchmarks in
  the |benchmarks| list.

  If json_pipe is available, a json file with the following contents will be
  written:
  [
      {
          "name": <string>,
          "description": <string>,
          "enabled": <boolean>,
          "story_tags": [
              <string>,
              ...
          ]
          ...
      },
      ...
  ]

  Args:
    benchmarks: the list of benchmarks to be printed (in the same order of the
      list).
    possible_browser: the possible_browser instance that's used for checking
      which benchmarks are enabled.
    output_pipe: the stream in which benchmarks are printed on.
    json_pipe: if available, also serialize the list into json_pipe.
  """
  if output_pipe is None:
    output_pipe = sys.stdout

  if not benchmarks:
    print >> output_pipe, 'No benchmarks found!'
    if json_pipe:
      print >> json_pipe, '[]'
    return

  bad_benchmark = next((b for b in benchmarks
                        if not issubclass(b, benchmark.Benchmark)), None)
  assert bad_benchmark is None, (
      '|benchmarks| param contains non benchmark class: %s' % bad_benchmark)

  all_benchmark_info = []
  for b in benchmarks:
    benchmark_info = {'name': b.Name(), 'description': b.Description()}
    benchmark_info['enabled'] = (
        not possible_browser or
        _IsBenchmarkEnabled(b, possible_browser, expectations_file))
    benchmark_info['stories'] = _GetStoriesWithTags(b)
    all_benchmark_info.append(benchmark_info)

  # Align the benchmark names to the longest one.
  format_string = '  %%-%ds %%s' % max(len(b['name'])
                                       for b in all_benchmark_info)

  # Sort the benchmarks by benchmark name.
  all_benchmark_info.sort(key=lambda b: b['name'])

  enabled = [b for b in all_benchmark_info if b['enabled']]
  if enabled:
    print >> output_pipe, 'Available benchmarks %sare:' % (
        'for %s ' % possible_browser.browser_type if possible_browser else '')
    for b in enabled:
      print >> output_pipe, format_string % (b['name'], b['description'])

  disabled = [b for b in all_benchmark_info if not b['enabled']]
  if disabled:
    print >> output_pipe, (
        '\nDisabled benchmarks for %s are (force run with -d):' %
        possible_browser.browser_type)
    for b in disabled:
      print >> output_pipe, format_string % (b['name'], b['description'])

  print >> output_pipe, (
      'Pass --browser to list benchmarks for another browser.\n')

  if json_pipe:
    print >> json_pipe, json.dumps(all_benchmark_info, indent=4,
                                   sort_keys=True, separators=(',', ': ')),


class List(command_line.OptparseCommand):
  """Lists the available benchmarks"""

  usage = '[benchmark_name] [<options>]'

  @classmethod
  def AddCommandLineArgs(cls, parser, _):
    parser.add_option('--json', action='store', dest='json_filename',
                      help='Output the list in JSON')

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('%%prog %s %s' % (cls.Name(), cls.usage))
    return parser

  @classmethod
  def ProcessCommandLineArgs(cls, parser, options, environment):
    if environment.expectations_files:
      assert len(environment.expectations_files) == 1
      expectations_file = environment.expectations_files[0]
    else:
      expectations_file = None
    if not options.positional_args:
      options.benchmarks = environment.GetBenchmarks()
    elif len(options.positional_args) == 1:
      options.benchmarks = _FuzzyMatchBenchmarkNames(
          options.positional_args[0], environment.GetBenchmarks())
    else:
      parser.error('Must provide at most one benchmark name.')
    cls._expectations_file = expectations_file

  def Run(self, options):
    # Set at least log info level for List command.
    # TODO(nedn): remove this once crbug.com/656224 is resolved. The recipe
    # should be change to use verbose logging instead.
    logging.getLogger().setLevel(logging.INFO)
    possible_browser = browser_finder.FindBrowser(options)
    if options.json_filename:
      with open(options.json_filename, 'w') as json_out:
        PrintBenchmarkList(options.benchmarks, possible_browser,
                           self._expectations_file,
                           json_pipe=json_out)
    else:
      PrintBenchmarkList(options.benchmarks, possible_browser,
                         self._expectations_file)
    return 0


class Run(command_line.OptparseCommand):
  """Run one or more benchmarks (default)"""

  usage = 'benchmark_name [<options>]'

  @classmethod
  def CreateParser(cls):
    options = browser_options.BrowserFinderOptions()
    parser = options.CreateParser('%%prog %s %s' % (cls.Name(), cls.usage))
    return parser

  @classmethod
  def AddCommandLineArgs(cls, parser, environment):
    benchmark.AddCommandLineArgs(parser)

    # Allow benchmarks to add their own command line options.
    matching_benchmarks = []
    for arg in sys.argv[1:]:
      matching_benchmark = environment.GetBenchmarkByName(arg)
      if matching_benchmark is not None:
        matching_benchmarks.append(matching_benchmark)

    if matching_benchmarks:
      # TODO(dtu): After move to argparse, add command-line args for all
      # benchmarks to subparser. Using subparsers will avoid duplicate
      # arguments.
      matching_benchmark = matching_benchmarks.pop()
      matching_benchmark.AddCommandLineArgs(parser)
      # The benchmark's options override the defaults!
      matching_benchmark.SetArgumentDefaults(parser)

  @classmethod
  def ProcessCommandLineArgs(cls, parser, options, environment):
    all_benchmarks = environment.GetBenchmarks()
    if environment.expectations_files:
      assert len(environment.expectations_files) == 1
      expectations_file = environment.expectations_files[0]
    else:
      expectations_file = None
    if not options.positional_args:
      possible_browser = (browser_finder.FindBrowser(options)
                          if options.browser_type else None)
      PrintBenchmarkList(
          all_benchmarks, possible_browser, expectations_file)
      parser.error('missing required argument: benchmark_name')

    benchmark_name = options.positional_args[0]
    benchmark_class = environment.GetBenchmarkByName(benchmark_name)
    if benchmark_class is None:
      most_likely_matched_benchmarks = matching.GetMostLikelyMatchedObject(
          all_benchmarks, benchmark_name, lambda x: x.Name())
      if most_likely_matched_benchmarks:
        print >> sys.stderr, 'Do you mean any of those benchmarks below?'
        PrintBenchmarkList(most_likely_matched_benchmarks, None,
                           expectations_file, sys.stderr)
      parser.error('no such benchmark: %s' % benchmark_name)

    if len(options.positional_args) > 1:
      parser.error(
          'unrecognized arguments: %s' % ' '.join(options.positional_args[1:]))

    assert issubclass(benchmark_class,
                      benchmark.Benchmark), ('Trying to run a non-Benchmark?!')

    benchmark.ProcessCommandLineArgs(parser, options)
    benchmark_class.ProcessCommandLineArgs(parser, options)

    cls._benchmark = benchmark_class
    cls._expectations_path = expectations_file

  def Run(self, options):
    b = self._benchmark()
    _SetExpectations(b, self._expectations_path)
    return min(255, b.Run(options))


def _FuzzyMatchBenchmarkNames(benchmark_name, benchmark_classes):
  def _Matches(input_string, search_string):
    if search_string.startswith(input_string):
      return True
    for part in search_string.split('.'):
      if part.startswith(input_string):
        return True
    return False

  return [
      cls for cls in benchmark_classes if _Matches(benchmark_name, cls.Name())]
