# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import

import time
import urllib.parse as encoder
from dashboard.common import namespaced_stored_object

PUBLIC_HOST = 'https://perf.luci.app'
# TODO: Add the internal host once it is ready
INTERNAL_HOST = '<PLACEHOLDER INTERNAL HOST>'


def GetSkiaUrlForRegression(regression, crrev_service, gitiles_service):
  repositories = namespaced_stored_object.Get('repositories')
  repo_url = repositories['chromium']['repository_url']

  def GetCommitInfo(revision):
    crrev_result = crrev_service.GetNumbering(
        number=revision,
        numbering_identifier='refs/heads/main',
        numbering_type='COMMIT_POSITION',
        project='chromium',
        repo='chromium/src')
    git_hash = crrev_result['git_sha']
    return gitiles_service.CommitInfo(repo_url, git_hash)

  start_commit_info = GetCommitInfo(regression.start_revision)
  end_commit_info = GetCommitInfo(regression.end_revision)
  if start_commit_info and start_commit_info.get('committer') and \
      end_commit_info and end_commit_info.get('committer'):
    begin_date = start_commit_info['committer']['time']
    end_date = end_commit_info['committer']['time']

    def GetTimeInt(timestamp: str):
      t = time.strptime(timestamp)
      return int(time.mktime(t))

    begin = GetTimeInt(begin_date)
    end = GetTimeInt(end_date)
    query_str = encoder.quote(
        'benchmark=%s&bot=%s&test=%s&subtest_1=%s' %
        (regression.benchmark_name, regression.bot_name,
         regression.test.test_part1_name, regression.test.test_part2_name))
    request_params_str = 'begin=%s&end=%s&numCommits=500&queries=%s' % (
        begin, end, query_str)
    internal_only = bool(regression.internal_only)
    host = INTERNAL_HOST if internal_only else PUBLIC_HOST
    return '%s/e/?%s' % (host, request_params_str)

  return ''
