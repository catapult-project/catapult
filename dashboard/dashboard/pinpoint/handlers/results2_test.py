# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import mock

from dashboard.pinpoint.handlers import results2
from dashboard.pinpoint.models.results2 import Results2Error
from dashboard.pinpoint import test


class _Results2Test(test.TestCase):

  def setUp(self):
    super(_Results2Test, self).setUp()

    self._job_from_id = mock.MagicMock()
    patcher = mock.patch.object(results2.job_module, 'JobFromId',
                                self._job_from_id)
    self.addCleanup(patcher.stop)
    patcher.start()

  def _SetJob(self, job):
    self._job_from_id.return_value = job


class Results2GetTest(_Results2Test):

  def testGet_InvalidJob_Error(self):
    self._SetJob(None)

    response = self.testapp.get('/api/results2/456', status=400)
    self.assertIn('Error', response.body)

  @mock.patch.object(results2.results2, 'GetCachedResults2',
                     mock.MagicMock(return_value=None))
  @mock.patch.object(results2.results2, 'ScheduleResults2Generation',
                     mock.MagicMock(return_value=False))
  def testGet_NotStarted_Incomplete(self):
    self._SetJob(_JobStub('456', started=False))

    result = json.loads(self.testapp.get('/api/results2/456').body)
    self.assertEqual('job-incomplete', result['status'])

  @mock.patch.object(results2.results2, 'GetCachedResults2',
                     mock.MagicMock(return_value='foo'))
  def testGet_AlreadyRunning_UsesCached(self):
    self._SetJob(_JobStub('456'))

    result = json.loads(self.testapp.get('/api/results2/456').body)
    self.assertEqual('complete', result['status'])
    self.assertEqual('foo', result['url'])

  @mock.patch.object(results2.results2, 'GetCachedResults2',
                     mock.MagicMock(return_value=None))
  @mock.patch.object(results2.results2, 'ScheduleResults2Generation',
                     mock.MagicMock(return_value=True))
  def testGet_Schedule_Succeeds(self):
    self._SetJob(_JobStub('456'))

    result = json.loads(self.testapp.get('/api/results2/456').body)
    self.assertEqual('pending', result['status'])

  @mock.patch.object(results2.results2, 'GetCachedResults2',
                     mock.MagicMock(return_value=None))
  @mock.patch.object(results2.results2, 'ScheduleResults2Generation',
                     mock.MagicMock(return_value=False))
  def testGet_Schedule_Fails(self):
    self._SetJob(_JobStub('456'))

    result = json.loads(self.testapp.get('/api/results2/456').body)
    self.assertEqual('failed', result['status'])


@mock.patch.object(results2.results2, 'GenerateResults2')
class Results2GeneratorPostTest(_Results2Test):

  def testGet_CallsGenerate(self, mock_generate):
    self._SetJob(_JobStub('789'))
    self.testapp.post('/api/generate-results2/789')
    self.assertTrue(mock_generate.called)

  def testGet_ReturnsError(self, mock_generate):
    mock_generate.side_effect = Results2Error('foo')
    self._SetJob(_JobStub('101112'))

    response = self.testapp.post('/api/generate-results2/101112')
    self.assertIn('foo', response.body)


class _TaskStub(object):
  pass


class _JobStub(object):

  def __init__(self, job_id, started=True, task=None):
    self.job_id = job_id
    self.task = task
    self.started = started

  @property
  def completed(self):
    return self.started and not self.task

