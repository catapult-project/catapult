#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import csv
import inspect
import logging
import os
import sys
import traceback

from telemetry import browser_finder
from telemetry import browser_options
from telemetry import multi_page_benchmark
from telemetry import page_runner
from telemetry import page_set


def _Discover(start_dir, clazz):
  """Discover all classes in |start_dir| which subclass |clazz|.

  Args:
    start_dir: The directory to recursively search.
    clazz: The base class to search for.

  Returns:
    dict of {module_name: class}.
  """
  top_level_dir = os.path.join(start_dir, '..')
  classes = {}
  for dirpath, _, filenames in os.walk(start_dir):
    for filename in filenames:
      if not filename.endswith('.py'):
        continue
      name, _ = os.path.splitext(filename)
      relpath = os.path.relpath(dirpath, top_level_dir)
      fqn = relpath.replace('/', '.') + '.' + name
      try:
        module = __import__(fqn, fromlist=[True])
      except Exception:
        logging.error('While importing [%s]\n' % fqn)
        traceback.print_exc()
        continue
      for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj):
          if clazz in inspect.getmro(obj):
            name = module.__name__.split('.')[-1]
            classes[name] = obj
  return classes


def Main(benchmark_dir):
  """Turns a MultiPageBenchmark into a command-line program.

  Args:
    benchmark_dir: Path to directory containing MultiPageBenchmarks.
  """
  benchmarks = _Discover(benchmark_dir, multi_page_benchmark.MultiPageBenchmark)

  # Naively find the benchmark. If we use the browser options parser, we run
  # the risk of failing to parse if we use a benchmark-specific parameter.
  benchmark_name = None
  for arg in sys.argv:
    if arg in benchmarks:
      benchmark_name = arg

  options = browser_options.BrowserOptions()
  parser = options.CreateParser('%prog [options] <benchmark> <page_set>')

  benchmark = None
  if benchmark_name is not None:
    benchmark = benchmarks[benchmark_name]()
    benchmark.AddOptions(parser)

  _, args = parser.parse_args()

  if benchmark is None or len(args) != 2:
    parser.print_usage()
    import page_sets # pylint: disable=F0401
    print >> sys.stderr, 'Available benchmarks:\n%s\n' % ',\n'.join(
        sorted(benchmarks.keys()))
    print >> sys.stderr, 'Available page_sets:\n%s\n' % ',\n'.join(
        sorted([os.path.relpath(f)
                for f in page_sets.GetAllPageSetFilenames()]))
    sys.exit(1)

  ps = page_set.PageSet.FromFile(args[1])

  benchmark.CustomizeBrowserOptions(options)
  possible_browser = browser_finder.FindBrowser(options)
  if not possible_browser:
    print >> sys.stderr, """No browser found.\n
Use --browser=list to figure out which are available.\n"""
    sys.exit(1)

  results = multi_page_benchmark.CsvBenchmarkResults(csv.writer(sys.stdout))
  with page_runner.PageRunner(ps) as runner:
    runner.Run(options, possible_browser, benchmark, results)
  # When using an exact executable, assume it is a reference build for the
  # purpose of outputting the perf results.
  results.PrintSummary(options.browser_executable and '_ref' or '')

  if len(results.page_failures):
    logging.warning('Failed pages: %s', '\n'.join(
        [failure['page'].url for failure in results.page_failures]))
  return min(255, len(results.page_failures))
