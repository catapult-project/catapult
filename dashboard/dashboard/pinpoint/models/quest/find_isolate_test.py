# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from dashboard.pinpoint.models import isolate
from dashboard.pinpoint.models.change import change_test
from dashboard.pinpoint.models.quest import find_isolate
from dashboard.pinpoint import test


class FindIsolateQuestTest(unittest.TestCase):

  def testMissingBuilder(self):
    arguments = {'target': 'telemetry_perf_tests'}
    with self.assertRaises(TypeError):
      find_isolate.FindIsolate.FromDict(arguments)

  def testMissingTarget(self):
    arguments = {'builder': 'Mac Builder'}
    with self.assertRaises(TypeError):
      find_isolate.FindIsolate.FromDict(arguments)

  def testAllArguments(self):
    arguments = {
        'builder': 'Mac Builder',
        'target': 'telemetry_perf_tests',
    }
    expected = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    self.assertEqual(find_isolate.FindIsolate.FromDict(arguments), expected)


class _FindIsolateExecutionTest(test.TestCase):

  def setUp(self):
    super(_FindIsolateExecutionTest, self).setUp()

    change = change_test.Change(123)
    isolate.Put((
        ('Mac Builder', change, 'telemetry_perf_tests',
         'https://isolate.server', '7c7e90be'),
    ))

  def assertExecutionFailure(self, execution, exception_class):
    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertIsInstance(execution.exception, basestring)
    last_exception_line = execution.exception.splitlines()[-1]
    self.assertTrue(last_exception_line.startswith(exception_class.__name__))
    self.assertEqual(execution.result_arguments, {})

  def assertExecutionSuccess(self, execution):
    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertIsNone(execution.exception)


class IsolateLookupTest(_FindIsolateExecutionTest):

  def testIsolateLookupSuccess(self):
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution = quest.Start(change_test.Change(123))
    execution.Poll()

    expected_result_arguments = {
        'isolate_server': 'https://isolate.server',
        'isolate_hash': '7c7e90be',
    }
    expected_as_dict = {
        'completed': True,
        'exception': None,
        'details': [
            {
                'key': 'builder',
                'value': 'Mac Builder',
            },
            {
                'key': 'isolate',
                'value': '7c7e90be',
                'url': 'https://isolate.server/browse?digest=7c7e90be',
            },
        ],
    }
    self.assertExecutionSuccess(execution)
    self.assertEqual(execution.result_values, ())
    self.assertEqual(execution.result_arguments, expected_result_arguments)
    self.assertEqual(execution.AsDict(), expected_as_dict)


@mock.patch('dashboard.services.buildbucket_service.GetJobStatus')
@mock.patch('dashboard.services.buildbucket_service.Put')
class BuildTest(_FindIsolateExecutionTest):

  def testBuildLifecycle(self, put, get_job_status):
    change = change_test.Change(123, 456, patch=True)
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution = quest.Start(change)

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    self.assertFalse(execution.completed)
    put.assert_called_once_with(find_isolate.BUCKET, {
        'builder_name': 'Mac Builder',
        'properties': {
            'clobber': True,
            'parent_got_revision': 'commit_123',
            'deps_revision_overrides': {test.CATAPULT_URL: 'commit_456'},
            'patch_gerrit_url': 'https://codereview.com',
            'patch_issue': 567890,
            'patch_project': 'project/name',
            'patch_ref': 'refs/changes/90/567890/5',
            'patch_repository_url': test.CHROMIUM_URL,
            'patch_set': 5,
            'patch_storage': 'gerrit',
        }
    })

    # Check build status.
    get_job_status.return_value = {'build': {
        'status': 'STARTED',
        'url': 'build_url',
    }}
    execution.Poll()

    self.assertFalse(execution.completed)
    get_job_status.assert_called_once_with('build_id')

    # Look up isolate hash.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'url': 'build_url',
            'result_details_json': """{
                "properties": {
                    "got_revision_cp": "refs/heads/master@{#123}",
                    "isolate_server": "https://isolate.server",
                    "swarm_hashes_refs/heads/master(at){#123}_without_patch":
                        {"telemetry_perf_tests": "isolate git hash"}
                }
            }""",
        }
    }
    execution.Poll()

    expected_result_arguments = {
        'isolate_server': 'https://isolate.server',
        'isolate_hash': 'isolate git hash',
    }
    expected_as_dict = {
        'completed': True,
        'exception': None,
        'details': [
            {
                'key': 'builder',
                'value': 'Mac Builder',
            },
            {
                'key': 'build',
                'value': 'build_id',
                'url': 'build_url',
            },
            {
                'key': 'isolate',
                'value': 'isolate git hash',
                'url': 'https://isolate.server/browse?digest=isolate git hash',
            },
        ],
    }
    self.assertExecutionSuccess(execution)
    self.assertEqual(execution.result_values, ())
    self.assertEqual(execution.result_arguments, expected_result_arguments)
    self.assertEqual(execution.AsDict(), expected_as_dict)

  def testSimultaneousBuilds(self, put, get_job_status):
    # Two builds started at the same time on the same Change should reuse the
    # same build request.
    change = change_test.Change(0)
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution_1 = quest.Start(change)
    execution_2 = quest.Start(change)

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution_1.Poll()
    execution_2.Poll()

    self.assertFalse(execution_1.completed)
    self.assertFalse(execution_2.completed)
    self.assertEqual(put.call_count, 1)

    # Check build status.
    get_job_status.return_value = {'build': {'status': 'STARTED'}}
    execution_1.Poll()
    execution_2.Poll()

    self.assertFalse(execution_1.completed)
    self.assertFalse(execution_2.completed)
    self.assertEqual(get_job_status.call_count, 2)

    # Look up isolate hash.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': """{
                "properties": {
                    "got_revision_cp": "refs/heads/master@{#123}",
                    "isolate_server": "https://isolate.server",
                    "swarm_hashes_refs/heads/master(at){#123}_without_patch":
                        {"telemetry_perf_tests": "isolate git hash"}
                }
            }""",
        }
    }
    execution_1.Poll()
    execution_2.Poll()

    self.assertExecutionSuccess(execution_1)
    self.assertExecutionSuccess(execution_2)

  def testBuildFailure(self, put, get_job_status):
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution = quest.Start(change_test.Change(0))

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    # Check build status.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'FAILURE',
            'failure_reason': 'BUILD_FAILURE',
        }
    }
    execution.Poll()

    self.assertExecutionFailure(execution, find_isolate.BuildError)

  def testBuildCanceled(self, put, get_job_status):
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution = quest.Start(change_test.Change(0))

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    # Check build status.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'CANCELED',
            'cancelation_reason': 'TIMEOUT',
        }
    }
    execution.Poll()

    self.assertExecutionFailure(execution, find_isolate.BuildError)

  def testBuildSucceededButIsolateIsMissing(self, put, get_job_status):
    quest = find_isolate.FindIsolate('Mac Builder', 'telemetry_perf_tests')
    execution = quest.Start(change_test.Change(0))

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    # Check build status.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': """{
                "properties": {
                    "got_revision_cp": "refs/heads/master@{#123}",
                    "isolate_server": "https://isolate.server",
                    "swarm_hashes_refs/heads/master(at){#123}_without_patch": {}
                }
            }""",
        }
    }
    with self.assertRaises(find_isolate.IsolateNotFoundError):
      execution.Poll()
