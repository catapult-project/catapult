# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import collections
import unittest

import mock

from dashboard.pinpoint import test
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import errors
from dashboard.pinpoint.models import isolate
from dashboard.pinpoint.models import job as job_module
from dashboard.pinpoint.models import task as task_module
from dashboard.pinpoint.models.change import change_test
from dashboard.pinpoint.models.quest import find_isolate


FakeJob = collections.namedtuple('Job',
                                 ['job_id', 'url', 'comparison_mode', 'user'])


class FindIsolateQuestTest(unittest.TestCase):

  def testMissingBuilder(self):
    arguments = {
        'builder': 'Mac Builder',
        'target': 'telemetry_perf_tests',
        'bucket': 'luci.bucket'
    }
    del arguments['builder']
    with self.assertRaises(TypeError):
      find_isolate.FindIsolate.FromDict(arguments)

  def testMissingTarget(self):
    arguments = {
        'builder': 'Mac Builder',
        'target': 'telemetry_perf_tests',
        'bucket': 'luci.bucket'
    }
    del arguments['target']
    with self.assertRaises(TypeError):
      find_isolate.FindIsolate.FromDict(arguments)

  def testMissingBucket(self):
    arguments = {
        'builder': 'Mac Builder',
        'target': 'telemetry_perf_tests',
        'bucket': 'luci.bucket'
    }
    del arguments['bucket']
    with self.assertRaises(TypeError):
      find_isolate.FindIsolate.FromDict(arguments)

  def testAllArguments(self):
    arguments = {
        'builder': 'Mac Builder',
        'target': 'telemetry_perf_tests',
        'bucket': 'luci.bucket'
    }
    expected = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
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
    self.assertIsInstance(execution.exception['traceback'], basestring)
    last_exception_line = execution.exception['traceback'].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith(exception_class.__name__))
    self.assertEqual(execution.result_arguments, {})

  def assertExecutionSuccess(self, execution):
    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertIsNone(execution.exception)


class IsolateLookupTest(_FindIsolateExecutionTest):

  def testIsolateLookupSuccess(self):
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')

    # Propagate a thing that looks like a job.
    quest.PropagateJob(
        FakeJob('cafef00d', 'https://pinpoint/cafef00d', 'performance',
                'user@example.com'))

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

  def testBuildNoReviewUrl(self, put, _):
    change = change_test.Change(123, 456, patch=True)
    results = change.base_commit.AsDict()
    del results['review_url']
    change.base_commit.AsDict = mock.MagicMock(return_value=results)

    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
    execution = quest.Start(change)
    del execution._bucket

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    self.assertExecutionFailure(execution, errors.BuildGerritUrlNotFound)

  def testBuildNoBucket(self, put, _):
    change = change_test.Change(123, 456, patch=True)
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
    execution = quest.Start(change)
    del execution._bucket

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    self.assertFalse(execution.completed)
    put.assert_called_once_with(
        find_isolate.BUCKET,
        [
            'buildset:patch/gerrit/codereview.com/567890/5',
            'buildset:commit/gitiles/chromium.googlesource.com/'
            'project/name/+/commit_123'
        ],
        {
            'builder_name': 'Mac Builder',
            'properties': {
                'clobber': True,
                'revision': 'commit_123',
                'deps_revision_overrides': {test.CATAPULT_URL: 'commit_456'},
                'patch_gerrit_url': 'https://codereview.com',
                'patch_issue': 567890,
                'patch_project': 'project/name',
                'patch_ref': 'refs/changes/90/567890/5',
                'patch_repository_url': test.CHROMIUM_URL,
                'patch_set': 5,
                'patch_storage': 'gerrit',
            }
        },
        None
    )

  def testBuildLifecycle(self, put, get_job_status):
    change = change_test.Change(123, 456, patch=True)
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
    # Propagate a thing that looks like a job.
    quest.PropagateJob(
        FakeJob('cafef00d', 'https://pinpoint/cafef00d', 'performance',
                'user@example.com'))
    execution = quest.Start(change)

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    self.assertFalse(execution.completed)
    put.assert_called_once_with(
        'luci.bucket',
        [
            'buildset:patch/gerrit/codereview.com/567890/5',
            'buildset:commit/gitiles/chromium.googlesource.com/'
            'project/name/+/commit_123',
            'pinpoint_job_id:cafef00d',
            'pinpoint_user:user@example.com',
            'pinpoint_url:https://pinpoint/cafef00d',
        ],
        {
            'builder_name': 'Mac Builder',
            'properties': {
                'clobber': True,
                'revision': 'commit_123',
                'deps_revision_overrides': {test.CATAPULT_URL: 'commit_456'},
                'patch_gerrit_url': 'https://codereview.com',
                'patch_issue': 567890,
                'patch_project': 'project/name',
                'patch_ref': 'refs/changes/90/567890/5',
                'patch_repository_url': test.CHROMIUM_URL,
                'patch_set': 5,
                'patch_storage': 'gerrit',
            },
        },
        {
            'topic': 'projects/chromeperf/topics/pinpoint-swarming-updates',
            'auth_token': 'UNUSED',
            'user_data': mock.ANY,
        }
    )

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
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
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
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
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

    self.assertExecutionFailure(execution, errors.BuildFailed)

  def testBuildCanceled(self, put, get_job_status):
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
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

    self.assertExecutionFailure(execution, errors.BuildCancelled)

  def testBuildSucceededButIsolateIsMissing(self, put, get_job_status):
    quest = find_isolate.FindIsolate(
        'Mac Builder', 'telemetry_perf_tests', 'luci.bucket')
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
    with self.assertRaises(errors.BuildIsolateNotFound):
      execution.Poll()


# The find_isolate Evaluator is special because it's meant to handle a "leaf"
# task in a graph, so we can test the evaluator on its own without setting up
# dependencies.
class FindIsolateEvaluatorBase(test.TestCase):

  def setUp(self):
    super(FindIsolateEvaluatorBase, self).setUp()
    self.maxDiff = None  # pylint: disable=invalid-name
    self.job = job_module.Job.New((), ())
    task_module.PopulateTaskGraph(
        self.job,
        task_module.TaskGraph(
            vertices=[
                task_module.TaskVertex(
                    id='build_7c7e90be',
                    vertex_type='find_isolate',
                    payload={
                        'builder': 'Mac Builder',
                        'target': 'telemetry_perf_tests',
                        'bucket': 'luci.bucket',
                        'change': {
                            'commits': [{
                                'repository': 'chromium',
                                'git_hash': '7c7e90be',
                            }],
                        },
                    })
            ],
            edges=[]))


@mock.patch('dashboard.services.buildbucket_service.GetJobStatus')
@mock.patch('dashboard.services.buildbucket_service.Put')
class FindIsolateEvaluatorTest(FindIsolateEvaluatorBase):

  def testInitiate_FoundIsolate(self, *_):
    # Seed the isolate for this change.
    change = change_module.Change(
        commits=[change_module.Commit('chromium', '7c7e90be')])
    isolate.Put((('Mac Builder', change, 'telemetry_perf_tests',
                  'https://isolate.server', '7c7e90be'),))

    # Then ensure that we can find the seeded isolate for the specified
    # revision.
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': 'https://isolate.server',
                'isolate_hash': '7c7e90be',
                'buildbucket_result': None,
                'buildbucket_job_status': None,
                'status': 'completed',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='initiate', target_task='build_7c7e90be', payload={}),
            find_isolate.Evaluator(self.job)))

  def testInitiate_ScheduleBuild(self, put, _):
    # We then need to make sure that the buildbucket put was called.
    put.return_value = {'build': {'id': '345982437987234'}}

    # This time we don't seed the isolate for the change to force the build.
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    },
                },
                'buildbucket_job_status': None,
                'status': 'ongoing',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='initiate', target_task='build_7c7e90be', payload={}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, put.call_count)

  def testUpdate_BuildSuccessful(self, put, get_build_status):
    # First we're going to initiate so we have a build scheduled.
    put.return_value = {'build': {'id': '345982437987234'}}
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': None,
                'status': 'ongoing',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='initiate', target_task='build_7c7e90be', payload={}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, put.call_count)

    # Now we send an update event which should cause us to poll the status of
    # the build on demand.
    json = """
    {
      "properties": {
          "got_revision_cp": "refs/heads/master@7c7e90be",
          "isolate_server": "https://isolate.server",
          "swarm_hashes_refs/heads/master(at)7c7e90be_without_patch":
              {"telemetry_perf_tests": "192923affe212adf"}
      }
    }"""
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': json,
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': 'https://isolate.server',
                'isolate_hash': '192923affe212adf',
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': mock.ANY,
                'status': 'completed',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

@mock.patch('dashboard.services.buildbucket_service.GetJobStatus')
class FindIsolateEvaluatorUpdateTests(FindIsolateEvaluatorBase):

  def setUp(self):
    super(FindIsolateEvaluatorUpdateTests, self).setUp()

    # Here we set up the pre-requisite for polling, where we've already had a
    # successful build scheduled.
    with mock.patch('dashboard.services.buildbucket_service.Put') as put:
      put.return_value = {'build': {'id': '345982437987234'}}
      self.assertDictEqual(
          {
              'build_7c7e90be': {
                  'isolate_server': None,
                  'isolate_hash': None,
                  'buildbucket_result': {
                      'build': {
                          'id': '345982437987234'
                      }
                  },
                  'buildbucket_job_status': None,
                  'status': 'ongoing',
              },
          },
          task_module.Evaluate(
              self.job,
              find_isolate.BuildEvent(
                  type='initiate', target_task='build_7c7e90be', payload={}),
              find_isolate.Evaluator(self.job)))
      self.assertEqual(1, put.call_count)

  def testUpdate_BuildFailed_HardFailure(self, get_build_status):
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'FAILURE',
            'result_details_json': '{}',
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': {
                    'status': 'COMPLETED',
                    'result': 'FAILURE',
                    'result_details_json': '{}',
                },
                'status': 'failed',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_BuildFailed_Cancelled(self, get_build_status):
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'CANCELLED',
            'result_details_json': '{}',
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': {
                    'status': 'COMPLETED',
                    'result': 'CANCELLED',
                    'result_details_json': '{}',
                },
                'status': 'cancelled',
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_MissingIsolates_Server(self, get_build_status):
    json = """
    {
      "properties": {
          "got_revision_cp": "refs/heads/master@7c7e90be",
          "swarm_hashes_refs/heads/master(at)7c7e90be_without_patch":
              {"telemetry_perf_tests": "192923affe212adf"}
      }
    }"""
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': json,
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': mock.ANY,
                'status': 'failed',
                'errors': mock.ANY,
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_MissingIsolates_Revision(self, get_build_status):
    json = """
    {
      "properties": {
          "isolate_server": "https://isolate.server",
          "swarm_hashes_refs/heads/master(at)7c7e90be_without_patch":
              {"telemetry_perf_tests": "192923affe212adf"}
      }
    }"""
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': json,
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': mock.ANY,
                'status': 'failed',
                'errors': mock.ANY,
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_MissingIsolates_Hashes(self, get_build_status):
    json = """
    {
      "properties": {
          "got_revision_cp": "refs/heads/master@7c7e90be",
          "isolate_server": "https://isolate.server"
      }
    }"""
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': json,
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': mock.ANY,
                'status': 'failed',
                'errors': mock.ANY,
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_MissingIsolates_InvalidJson(self, get_build_status):
    json = '{ invalid }'
    get_build_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
            'result_details_json': json,
        }
    }
    self.assertDictEqual(
        {
            'build_7c7e90be': {
                'isolate_server': None,
                'isolate_hash': None,
                'buildbucket_result': {
                    'build': {
                        'id': '345982437987234'
                    }
                },
                'buildbucket_job_status': mock.ANY,
                'status': 'failed',
                'errors': mock.ANY,
            },
        },
        task_module.Evaluate(
            self.job,
            find_isolate.BuildEvent(
                type='update',
                target_task='build_7c7e90be',
                payload={'status': 'build_completed'}),
            find_isolate.Evaluator(self.job)))
    self.assertEqual(1, get_build_status.call_count)

  def testUpdate_BuildFailed_ScheduleRetry(self, *_):
    self.skipTest('Not implemented yet.')
