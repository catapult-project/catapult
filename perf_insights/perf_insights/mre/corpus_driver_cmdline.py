# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from perf_insights.mre import local_directory_corpus_driver
from perf_insights.mre import perf_insights_corpus_driver


# TODO(simonhatch): Use telemetry's discover.py module once its part of
# catapult.
_CORPUS_DRIVERS = {
  'perf-insights': {
      'description': 'Use the performance insights server.',
      'class': perf_insights_corpus_driver.PerfInsightsCorpusDriver
  },
  'local-directory': {
      'description': 'Use traces from a local directory.',
      'class': local_directory_corpus_driver.LocalDirectoryCorpusDriver
  },
  'list': None
}
_CORPUS_DRIVER_DEFAULT = 'perf-insights'


def AddArguments(parser):
  parser.add_argument(
      '-c', '--corpus',
      choices=_CORPUS_DRIVERS.keys(),
      default=_CORPUS_DRIVER_DEFAULT)
  for k, v in _CORPUS_DRIVERS.iteritems():
    if not v:
      continue
    parser_group = parser.add_argument_group(k)
    driver_cls = v['class']
    driver_cls.AddArguments(parser_group)


def GetCorpusDriver(parser, args):
  # With parse_known_args, optional arguments aren't guaranteed to be there so
  # we need to check if it's there, and use the default otherwise.
  corpus = _CORPUS_DRIVER_DEFAULT
  if hasattr(args, 'corpus'):
    corpus = args.corpus

  if corpus == 'list':
    corpus_descriptions = '\n'.join(
        ['%s: %s' % (k, v['description'])
            for k, v in _CORPUS_DRIVERS.iteritems() if v]
      )
    parser.exit('Valid drivers:\n\n%s\n' % corpus_descriptions)

  cls = _CORPUS_DRIVERS[corpus]['class']
  init_args = cls.CheckAndCreateInitArguments(parser, args)
  return cls(**init_args)
