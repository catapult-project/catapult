# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import urllib
import urllib2

from perf_insights import corpus_driver
from perf_insights.mre import file_handle


_DEFAULT_PERF_INSIGHTS_SERVER = 'http://performance-insights.appspot.com'


class PerfInsightsCorpusDriver(corpus_driver.CorpusDriver):

  def __init__(self, cache_directory, server=_DEFAULT_PERF_INSIGHTS_SERVER):
    self.directory = cache_directory
    self.server = server

  @staticmethod
  def CheckAndCreateInitArguments(parser, args):
    cache_dir = os.path.abspath(os.path.expanduser(args.cache_directory))
    if not os.path.exists(cache_dir):
      parser.error('Trace directory does not exist')
      return None
    return {
      'cache_directory': cache_dir,
      'server': args.server
    }

  @staticmethod
  def AddArguments(parser):
    parser.add_argument(
        '--cache_directory',
        help='Local directory to cache traces.')
    parser.add_argument(
        '--server',
        help='Server address of perf insights.',
        default=_DEFAULT_PERF_INSIGHTS_SERVER)

  def GetTraceHandlesMatchingQuery(self, query):
    trace_handles = []

    query_string = urllib.quote_plus(query.AsQueryString())
    response = urllib2.urlopen(
        '%s/query?q=%s' % (self.server, query_string))
    file_urls = json.loads(response.read())

    for file_url in file_urls:
      th = file_handle.GCSFileHandle(file_url, self.directory)
      trace_handles.append(th)

    return trace_handles

