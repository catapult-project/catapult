# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

from typing import List, Optional

import datetime
import logging
import urllib.parse as encoder

REPOSITORY_HOST_MAPPING = {
    'chromium': {
        'public_host':
            'https://perf.luci.app',
        'internal_host':
            'https://chrome-perf.corp.goog',
        'masters': [
            'ChromeFYIInternal',
            'ChromiumAndroid',
            'ChromiumChrome',
            'ChromiumChromiumos',
            'ChromiumClang',
            'ChromiumFuchsia',
            'ChromiumGPUFYI',
            'ChromiumPerf',
            'ChromiumPerfFyi',
            'ChromiumPerfPGO',
            'TryServerChromiumFuchsia',
            'TryserverChromiumChromiumOS',
            'ChromiumFuchsiaFyi',
            'TryserverChromiumAndroid',
            'ChromiumAndroidFyi',
            'ChromiumFYI',
            'ChromiumPerfFyi.all',
            'ChromiumGPU',
        ]
    },
    'webrtc': {
        'public_host': 'https://webrtc-perf.luci.app',
        'internal_host': None,
        'masters': ['WebRTCPerf']
    }
}

QUERY_TEST_LIMIT = 5


def GetSkiaUrl(start_time: datetime.datetime,
               end_time: datetime.datetime,
               master: str,
               bots: Optional[List[str]] = None,
               benchmarks: Optional[List[str]] = None,
               tests: Optional[List[str]] = None,
               subtests_1: Optional[List[str]] = None,
               subtests_2: Optional[List[str]] = None,
               internal_only: bool = True,
               num_points: int = 500):
  host = None
  for repo_map in REPOSITORY_HOST_MAPPING.values():
    if master in repo_map['masters']:
      host = repo_map['internal_host'] if internal_only else repo_map[
          'public_host']
      break
  if not host:
    logging.warning(
        'Skia instance does not exist for master %s and internal_only=%s',
        master, internal_only)
    return None

  def _FormatList(lst):
    # Converts None into empty lists.
    # Remove duplicates while preserving order, as opposed to using set.

    if lst == None:
      return []

    return list(dict.fromkeys(lst))

  benchmark_query_str = ''.join(
      '&benchmark=%s' % benchmark for benchmark in _FormatList(benchmarks))
  bot_query_str = ''.join('&bot=%s' % bot for bot in _FormatList(bots))
  test_query_str = ''.join('&test=%s' % test for test in _FormatList(tests))
  subtest_1_query_str = ''.join(
      '&subtest_1=%s' % subtest for subtest in _FormatList(subtests_1))
  subtest_2_query_str = ''.join(
      '&subtest_2=%s' % subtest for subtest in _FormatList(subtests_2))

  query_str = encoder.quote('stat=value%s%s%s%s%s' %
                            (benchmark_query_str, bot_query_str, test_query_str,
                             subtest_1_query_str, subtest_2_query_str))
  return _GenerateUrl(host, query_str, start_time, end_time, num_points)


def GetSkiaUrlForAlertGroup(alert_group_id: str,
                            internal_only: bool,
                            project_id: str = 'chromium'):
  if project_id not in REPOSITORY_HOST_MAPPING.keys():
    raise RuntimeError('Project Id not supported in Skia: %s ' % project_id)

  hosts = REPOSITORY_HOST_MAPPING[project_id]

  host = hosts['internal_host'] if internal_only else hosts['public_host']
  if not host:
    raise RuntimeError('Project Id %s has no host where internal_only=%s' %
                       (project_id, str(internal_only)))

  return '%s/_/alertgroup?group_id=%s' % (host, alert_group_id)


def _GenerateUrl(host: str, query_str: str, begin_date: datetime.datetime,
                 end_date: datetime.datetime, num_commits: int):
  request_params_str = 'numCommits=%i' % num_commits
  if begin_date:
    begin = _GetTimeInt(begin_date)
    request_params_str += '&begin=%i' % begin
  if end_date:
    end = _GetTimeInt(end_date)
    request_params_str += '&end=%i' % end
  request_params_str += '&queries=%s' % query_str
  return '%s/e/?%s' % (host, request_params_str)


def _GetTimeInt(date: datetime.datetime):
  epoch = datetime.datetime.utcfromtimestamp(0)
  int_timestamp = (date - epoch) // datetime.timedelta(seconds=1)
  return int_timestamp
