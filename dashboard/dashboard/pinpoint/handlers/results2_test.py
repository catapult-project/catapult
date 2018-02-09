# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

import webapp2
import webtest

from dashboard.pinpoint.handlers import results2


_ATTEMPT_DATA = {
    "executions": [{"result_arguments": {"isolate_hash": "e26a40a0d4"}}]
}


_JOB_NO_DIFFERENCES = {
    "changes": [{}, {}, {}, {}],
    "quests": ["Test"],
    "comparisons": ["same", "same", "same"],
    "attempts": [
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
    ],
}


_JOB_WITH_DIFFERENCES = {
    "changes": [{}, {}, {}, {}],
    "quests": ["Test"],
    "comparisons": ["same", "different", "different"],
    "attempts": [
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
        [_ATTEMPT_DATA],
    ],
}


_JOB_MISSING_EXECUTIONS = {
    "changes": [{}, {}],
    "quests": ["Test"],
    "comparisons": ["same"],
    "attempts": [
        [_ATTEMPT_DATA, {"executions": []}],
        [{"executions": []}, _ATTEMPT_DATA],
    ],
}


class _Results2Test(unittest.TestCase):

  def setUp(self):
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/results2/<job_id>', results2.Results2),
    ])
    self.testapp = webtest.TestApp(app)
    self.testapp.extra_environ.update({'REMOTE_ADDR': 'remote_ip'})

    self._job_from_id = mock.MagicMock()
    patcher = mock.patch.object(results2.job_module, 'JobFromId',
                                self._job_from_id)
    self.addCleanup(patcher.stop)
    patcher.start()

  def _SetJob(self, job):
    self._job_from_id.return_value = job


class FailureTest(_Results2Test):

  def testGet_InvalidJob(self):
    self._SetJob(None)
    response = self.testapp.get('/results2/123', status=400)
    self.assertIn('Error', response.body)

  def testGet_JobHasNoTestQuest(self):
    self._SetJob(_JobStub({'quests': []}))
    response = self.testapp.get('/results2/123', status=400)
    self.assertIn('No Test quest', response.body)


@mock.patch.object(results2.read_value, '_RetrieveOutputJson',
                   mock.MagicMock(return_value=['a']))
@mock.patch.object(results2, 'open', mock.mock_open(read_data='fake_viewer'),
                   create=True)
@mock.patch.object(results2.render_histograms_viewer, 'RenderHistogramsViewer')
class SuccessTest(_Results2Test):

  def testGet_NoDifferences(self, mock_render):
    self._SetJob(_JobStub(_JOB_NO_DIFFERENCES))
    self.testapp.get('/results2/123')
    mock_render.assert_called_with(
        ['a', 'a', 'a', 'a'], mock.ANY, vulcanized_html='fake_viewer')

  def testGet_WithDifferences(self, mock_render):
    self._SetJob(_JobStub(_JOB_WITH_DIFFERENCES))
    self.testapp.get('/results2/123')
    mock_render.assert_called_with(
        ['a', 'a', 'a'], mock.ANY, vulcanized_html='fake_viewer')

  def testGet_MissingExecutions(self, mock_render):
    self._SetJob(_JobStub(_JOB_MISSING_EXECUTIONS))
    self.testapp.get('/results2/123')
    mock_render.assert_called_with(
        ['a', 'a'], mock.ANY, vulcanized_html='fake_viewer')


class _JobStub(object):

  def __init__(self, job_dict):
    self._job_dict = job_dict

  def AsDict(self, options=None):
    del options
    return self._job_dict
