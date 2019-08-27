# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Output formatter for JSON Test Results Format.

See
https://chromium.googlesource.com/chromium/src/+/master/docs/testing/json_test_results_format.md
for details.
"""

import collections
import json
import os

from telemetry.internal.results import output_formatter


def _mk_dict(d, *args):
  for key in args:
    if key not in d:
      d[key] = {}
    d = d[key]
  return d


def ResultsAsDict(results):
  """Takes PageTestResults to a dict in the JSON test results format.

  To serialize results as JSON we first convert them to a dict that can be
  serialized by the json module.

  Args:
    results: a PageTestResults object
  """
  result_dict = {
      'interrupted': results.benchmark_interrupted,
      'path_delimiter': '/',
      'version': 3,
      'seconds_since_epoch': results.benchmark_start_us / 1e6,
      'tests': {},
  }
  status_counter = collections.Counter()
  for run in results.IterStoryRuns():
    status = run.status
    expected = status if run.is_expected else 'PASS'
    status_counter[status] += 1

    test = _mk_dict(
        result_dict, 'tests', results.benchmark_name, run.story.name)
    if 'actual' not in test:
      test['actual'] = status
    else:
      test['actual'] += (' ' + status)

    if 'expected' not in test:
      test['expected'] = expected
    else:
      if expected not in test['expected']:
        test['expected'] += (' ' + expected)

    if 'is_unexpected' not in test:
      test['is_unexpected'] = status != expected
    else:
      test['is_unexpected'] = test['is_unexpected'] or status != expected

    if 'time' not in test:
      test['time'] = run.duration
      test['times'] = [run.duration]
    else:
      test['times'].append(run.duration)

    for artifact in run.IterArtifacts():
      if artifact.url is not None:
        artifact_path = artifact.url
      else:
        # Paths in json format should be relative to the output directory and
        # '/'-delimited on all platforms according to the spec.
        relative_path = os.path.relpath(os.path.realpath(artifact.local_path),
                                        os.path.realpath(results.output_dir))
        artifact_path = relative_path.replace(os.sep, '/')

      test.setdefault('artifacts', {}).setdefault(artifact.name, []).append(
          artifact_path)

    # Shard index is really only useful for failed tests. See crbug.com/960951
    # for details.
    if run.failed and 'GTEST_SHARD_INDEX' in os.environ:
      test['shard'] = int(os.environ['GTEST_SHARD_INDEX'])

  # The following logic can interfere with calculating flakiness percentages.
  # The logic does allow us to re-run tests without them automatically
  # being marked as flaky by the flakiness dashboard and milo.
  # Note that it does not change the total number of passes in
  # num_failures_by_type
  # crbug.com/754825
  for _, stories in result_dict['tests'].iteritems():
    for _, story_results in stories.iteritems():
      deduped_results = set(story_results['actual'].split(' '))
      if deduped_results == {'PASS'}:
        story_results['actual'] = 'PASS'
      elif deduped_results == {'SKIP'}:
        story_results['actual'] = 'SKIP'

  result_dict['num_failures_by_type'] = dict(status_counter)
  return result_dict


class JsonOutputFormatter(output_formatter.OutputFormatter):
  def Format(self, results):
    """Serialize page test results in JSON Test Results format."""
    json.dump(
        ResultsAsDict(results),
        self.output_stream, indent=2, sort_keys=True, separators=(',', ': '))
    self.output_stream.write('\n')
