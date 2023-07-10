# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

import datetime
import logging
import time
import urllib.parse as encoder
from dashboard.common import namespaced_stored_object

PUBLIC_HOST = 'https://perf.luci.app'
INTERNAL_HOST = 'https://chrome-perf.corp.goog'
SUPPORTED_REPOSITORIES = ['chromium']
QUERY_TEST_LIMIT = 5


def GetSkiaUrlForRegressionGroup(regressions, crrev_service, gitiles_service):
  # Filter out regressions that are only in the supported repositories
  filtered_regressions = []
  for r in regressions:
    if r.project_id and r.project_id in SUPPORTED_REPOSITORIES:
      filtered_regressions.append(r)

  if len(filtered_regressions) > 0:
    repositories = namespaced_stored_object.Get('repositories')
    repo_url = repositories['chromium']['repository_url']

    benchmarks = set()
    bots = set()
    tests = set()
    subtests_1 = set()
    start_revision = filtered_regressions[0].start_revision
    end_revision = filtered_regressions[0].end_revision

    for regression in filtered_regressions:
      regression_test = regression.test.get()
      benchmarks.add(regression.benchmark_name)
      bots.add(regression.bot_name)
      tests.add(regression_test.test_part1_name)
      if regression_test.test_part2_name:
        subtests_1.add(regression_test.test_part2_name)

      # Capture the earliest start_revision and latest end_revision from
      # the regressions group
      if regression.start_revision < start_revision:
        start_revision = regression.start_revision
      if regression.end_revision > end_revision:
        end_revision = regression.end_revision

      # Avoid adding too many plots to the graph and crowding it
      if len(tests) >= QUERY_TEST_LIMIT or len(subtests_1) >= QUERY_TEST_LIMIT:
        break

    benchmark_query_str = ''.join(
        '&benchmark=%s' % benchmark for benchmark in benchmarks)
    bot_query_str = ''.join('&bot=%s' % bot for bot in bots)
    test_query_str = ''.join('&test=%s' % test for test in tests)
    subtest_query_str = ''.join(
        '&subtest_1=%s' % subtest for subtest in subtests_1)

    query_str = encoder.quote(
        'stat=value%s%s%s%s' %
        (benchmark_query_str, bot_query_str, test_query_str, subtest_query_str))

    start_commit_info = _GetCommitInfo(start_revision, crrev_service,
                                       gitiles_service, repo_url)
    end_commit_info = _GetCommitInfo(end_revision, crrev_service,
                                     gitiles_service, repo_url)

    if start_commit_info and start_commit_info.get('committer') and \
        end_commit_info and end_commit_info.get('committer'):
      begin_date = start_commit_info['committer']['time']

      # For end date, add one day to the date in end_commit_info.
      # Otherwise the anomaly regression/improvement icon shows up right
      # at the end of the graph in the UI which isn't ideal.
      end_date_str = end_commit_info['committer']['time']
      end_date_obj = datetime.datetime.strptime(
          end_date_str, '%a %b %d %H:%M:%S %Y') + datetime.timedelta(days=1)
      end_date = str(end_date_obj)
      return _GenerateUrl(filtered_regressions[0].internal_only, query_str,
                          begin_date, end_date)
  return ''


def _GenerateUrl(internal_only: bool, query_str: str, begin_date, end_date):
  begin = _GetTimeInt(begin_date)
  end = _GetTimeInt(end_date)
  request_params_str = 'begin=%s&end=%s&numCommits=500&queries=%s' % (
      begin, end, query_str)
  host = INTERNAL_HOST if internal_only else PUBLIC_HOST
  return '%s/e/?%s' % (host, request_params_str)


def _GetCommitInfo(revision, crrev_service, gitiles_service, repo_url):
  logging.info('Getting commit position for revision %s', revision)
  crrev_result = crrev_service.GetNumbering(
      number=revision,
      numbering_identifier='refs/heads/main',
      numbering_type='COMMIT_POSITION',
      project='chromium',
      repo='chromium/src')
  git_hash = crrev_result['git_sha']
  return gitiles_service.CommitInfo(repo_url, git_hash)


def _GetTimeInt(timestamp: str):
  t = time.strptime(timestamp)
  return int(time.mktime(t))
