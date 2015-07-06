# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Small test to send a put request to buildbucket."""

import re

_LINUX_BISECTOR_BUILDER_NAME = 'linux_perf_bisector'


class BisectJob(object):
  """A buildbot bisect job started and monitored through buildbucket."""

  def __init__(self, platform, good_revision, bad_revision, test_command,
               metric, repeats, truncate, timeout_minutes, bug_id, gs_bucket,
               builder_host=None, builder_port=None, test_type='perf'):
    if not all([platform, good_revision, bad_revision, test_command, metric,
                repeats, timeout_minutes]):
      raise ValueError('At least one of the values required for BisectJob '
                       'construction was not given or was given with a None '
                       'value.')
    self.builder_name = BisectJob.GetBuilderForPlatform(platform)
    self.good_revision = good_revision
    self.bad_revision = bad_revision
    self.command = BisectJob.EnsureCommandPath(test_command)
    self.metric = metric
    self.repeat_count = repeats
    self.truncate_percent = truncate
    self.max_time_minutes = timeout_minutes
    self.bug_id = bug_id
    self.gs_bucket = gs_bucket
    self.builder_host = builder_host
    self.builder_port = builder_port
    self.test_type = test_type

  @staticmethod
  def EnsureCommandPath(command):
    old_perf_path_regex = re.compile(r'(?<!src/)tools/perf')
    if old_perf_path_regex.search(command):
      return old_perf_path_regex.sub('src/tools/perf', command)
    old_perf_path_regex_win = re.compile(r'(?<!src\\)tools\\perf')
    if old_perf_path_regex_win.search(command):
      return old_perf_path_regex_win.sub(r'src\\tools\\perf', command)
    return command

  @staticmethod
  def GetBuilderForPlatform(platform):
    """Maps builder names to the platforms they can bisect."""
    if platform == 'linux':
      return _LINUX_BISECTOR_BUILDER_NAME
    raise NotImplementedError('Only linux platform is currently supported.')

  def GetBuildParameters(self):
    """Prepares a nested dict containing the bisect config."""
    # TODO(robertocn): Some of these should be optional.
    bisect_config = {
        'test_type': self.test_type,
        'command': self.command,
        'good_revision': self.good_revision,
        'bad_revision': self.bad_revision,
        'metric': self.metric,
        'repeat_count': self.repeat_count,
        'max_time_minutes': self.max_time_minutes,
        'truncate_percent': self.truncate_percent,
        'bug_id': self.bug_id,
        'gs_bucket': self.gs_bucket,
        'builder_host': self.builder_host,
        'builder_port': self.builder_port,
    }
    properties = {'bisect_config': bisect_config}
    parameters = {
        'builder_name': self.builder_name,
        'properties': properties,
    }
    return parameters

  # TODO(robertocn): Add methods to query the status of a job form buildbucket.
  # TODO(robertocn): Add static method to get a job by it's buildbucket id.
  # TODO(robertocn): Add appropriate tests.
