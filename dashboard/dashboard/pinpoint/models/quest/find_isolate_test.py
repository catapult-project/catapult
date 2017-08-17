# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import mock

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.common import namespaced_stored_object
from dashboard.pinpoint.models import change as change_module
from dashboard.pinpoint.models import isolate
from dashboard.pinpoint.models.quest import find_isolate


class _FindIsolateTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

    change = change_module.Change(change_module.Dep('src', 'f9f2b720'))
    isolate.Put((
        ('Mac Builder', change, 'telemetry_perf_tests', '7c7e90be'),
    ))

    namespaced_stored_object.Set('repositories', {
        'src': {
            'repository_url': 'https://chromium.googlesource.com/chromium/src'
        },
        'v8': {
            'repository_url': 'https://chromium.googlesource.com/v8/v8'
        },
    })

  def tearDown(self):
    self.testbed.deactivate()

  def assertExecutionFailure(self, execution, exception_class):
    self.assertTrue(execution.completed)
    self.assertTrue(execution.failed)
    self.assertEqual(len(execution.result_values), 1)
    self.assertIsInstance(execution.result_values[0], basestring)
    last_exception_line = execution.result_values[0].splitlines()[-1]
    self.assertTrue(last_exception_line.startswith(exception_class.__name__))
    self.assertEqual(execution.result_arguments, {})

  def assertExecutionSuccess(self, execution):
    self.assertTrue(execution.completed)
    self.assertFalse(execution.failed)
    self.assertEqual(execution.result_values, (None,))


class IsolateLookupTest(_FindIsolateTest):

  def testIsolateLookupSuccess(self):
    change = change_module.Change(change_module.Dep('src', 'f9f2b720'))
    quest = find_isolate.FindIsolate('Mac Pro Perf', 'telemetry_perf_tests')
    execution = quest.Start(change)
    execution.Poll()

    self.assertExecutionSuccess(execution)
    self.assertEqual(execution.result_arguments, {'isolate_hash': '7c7e90be'})


class BuilderLookupTest(_FindIsolateTest):

  def testSuccesfulBuilderLookupForAllBuilders(self):
    builder_testers = (
        ('arm-builder-rel', 'health-plan-clankium-phone'),
        ('Android Builder', 'Android Nexus5 Perf'),
        ('Android arm64 Builder', 'Android Nexus5X Perf'),
        ('Linux Builder', 'Linux Perf'),
        ('Mac Builder', 'Mac Air Perf'),
        ('Win Builder', 'Win 7 Perf'),
        ('Win x64 Builder', 'Win Zenbook Perf'),
    )

    change = change_module.Change(change_module.Dep('src', 'git hash'))
    isolate.Put(
        (builder, change, 'telemetry_perf_tests', hex(hash(builder)))
        for builder, _ in builder_testers)

    for builder, tester in builder_testers:
      quest = find_isolate.FindIsolate(tester, 'telemetry_perf_tests')
      execution = quest.Start(change)
      execution.Poll()

      self.assertExecutionSuccess(execution)
      self.assertEqual(execution.result_arguments,
                       {'isolate_hash': hex(hash(builder))})

  def testUnknownBuilder(self):
    with self.assertRaises(NotImplementedError):
      find_isolate.FindIsolate('Unix Perf', 'telemetry_perf_tests')


@mock.patch('dashboard.services.buildbucket_service.GetJobStatus')
@mock.patch('dashboard.services.buildbucket_service.Put')
class BuildTest(_FindIsolateTest):

  def testBuildLifecycle(self, put, get_job_status):
    change = change_module.Change(
        change_module.Dep('src', 'base git hash'),
        (change_module.Dep('v8', 'dep git hash'),),
        patch=change_module.Patch('https://example.org', 2565263002, 20001))
    quest = find_isolate.FindIsolate('Mac Pro Perf', 'telemetry_perf_tests')
    execution = quest.Start(change)

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    self.assertFalse(execution.completed)
    put.assert_called_once_with(find_isolate.BUCKET, {
        'builder_name': 'Mac Builder',
        'properties': {
            'clobber': True,
            'parent_got_revision': 'base git hash',
            'deps_revision_overrides': {
                'https://chromium.googlesource.com/v8/v8': 'dep git hash',
            },
            'patch_storage': 'rietveld',
            'rietveld': 'https://example.org',
            'issue': 2565263002,
            'patchset': 20001,
        }
    })

    # Check build status.
    get_job_status.return_value = {'build': {'status': 'STARTED'}}
    execution.Poll()

    self.assertFalse(execution.completed)
    get_job_status.assert_called_once_with('build_id')

    # Look up isolate hash.
    isolate.Put((('Mac Builder', change,
                  'telemetry_perf_tests', 'isolate git hash'),))
    execution.Poll()

    self.assertExecutionSuccess(execution)

  def testBuildFailure(self, put, get_job_status):
    change = change_module.Change(
        change_module.Dep('src', 'base git hash'),
        (change_module.Dep('v8', 'dep git hash'),),
        patch=change_module.Patch('https://example.org', 2565263002, 20001))
    quest = find_isolate.FindIsolate('Mac Pro Perf', 'telemetry_perf_tests')
    execution = quest.Start(change)

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
    change = change_module.Change(
        change_module.Dep('src', 'base git hash'),
        (change_module.Dep('v8', 'dep git hash'),),
        patch=change_module.Patch('https://example.org', 2565263002, 20001))
    quest = find_isolate.FindIsolate('Mac Pro Perf', 'telemetry_perf_tests')
    execution = quest.Start(change)

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
    change = change_module.Change(
        change_module.Dep('src', 'base git hash'),
        (change_module.Dep('v8', 'dep git hash'),),
        patch=change_module.Patch('https://example.org', 2565263002, 20001))
    quest = find_isolate.FindIsolate('Mac Pro Perf', 'telemetry_perf_tests')
    execution = quest.Start(change)

    # Request a build.
    put.return_value = {'build': {'id': 'build_id'}}
    execution.Poll()

    # Check build status.
    get_job_status.return_value = {
        'build': {
            'status': 'COMPLETED',
            'result': 'SUCCESS',
        }
    }
    execution.Poll()

    self.assertExecutionFailure(execution, find_isolate.BuildError)
