# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import mock
import unittest

import webapp2
import webtest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.pinpoint.handlers import results2


_JOB_DATA = json.loads("""{
    "status": "Completed",
    "auto_explore": true,
    "updated": "2017-10-23T15:30:48.735320",
    "bug_id": 776741,
    "attempts": [
        [
            {
                "executions": [
                    {},
                    {
                        "result_arguments": {
                            "isolate_hash": "e26a40a0d4"
                        }
                    },
                    {}
                ]
            },
            {
                "executions": [
                    {},
                    {
                        "result_arguments": {
                            "isolate_hash": "83e9b6432e"
                        }
                    },
                    {}
                ]
            }
        ],
        [
            {
                "executions": [
                    {},
                    {
                        "result_arguments": {
                            "isolate_hash": "678eb8256b"
                        }
                    },
                    {}
                ]
            },
            {
                "executions": [
                    {},
                    {
                        "result_arguments": {
                            "isolate_hash": "c95da9ad1e"
                        }
                    },
                    {}
                ]
            }
        ]
    ],
    "result_values": [],
    "exception": null,
    "job_id": "16bde7af780000",
    "created": "2017-10-23T15:21:12.215800",
    "arguments": {},
    "quests": [
        "Build",
        "Test",
        "Values"
    ],
    "comparisons": [
        "same"
    ],
    "changes": [
        {
            "commits": [
                {
                    "url": "http://foo",
                    "git_hash": "8833d9a9b6b99a1c035fac53998629aa2b513cda",
                    "repository": "chromium"
                }
            ],
            "patch": null
        },
        {
            "commits": [
                {
                    "url": "http://foo",
                    "git_hash": "0e4ade6da647251e91094be95f952ebada19ce03",
                    "repository": "chromium"
                }
            ],
            "patch": null
        }
    ]
}""")

_HISTOGRAM_DATA = [
    {
        'binBoundaries': [1, [1, 1000, 20]],
        'diagnostics': {
        },
        'guid': '2a714c36-f4ef-488d-8bee-93c7e3149388',
        'name': 'foo2',
        'running': [3, 3, 0.5972531564093516, 2, 1, 6, 2],
        'sampleValues': [1, 2, 3],
        'unit': 'count'
    }
]


class Results2Test(unittest.TestCase):

  def setUp(self):
    app = webapp2.WSGIApplication([
        webapp2.Route(r'/results2/<job_id>', results2.Results2),
    ])
    self.testapp = webtest.TestApp(app)
    self.testapp.extra_environ.update({'REMOTE_ADDR': 'remote_ip'})

    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  @mock.patch.object(
      results2, '_GetJobData', mock.MagicMock(return_value=_JOB_DATA))
  @mock.patch.object(
      results2.read_value, '_RetrieveOutputJson',
      mock.MagicMock(return_value=None))
  @mock.patch.object(
      results2, '_ReadVulcanizedHistogramsViewer',
      mock.MagicMock(return_value='fake_viewer'))
  @mock.patch.object(
      results2.render_histograms_viewer, 'RenderHistogramsViewer')
  @mock.patch('uuid.uuid4', mock.MagicMock(return_value='fake_guid'))
  def testPost_RetrieveFails(self, mock_render):
    self.testapp.get('/results2/123')

    mock_render.assert_called_with(
        [], mock.ANY, vulcanized_html='fake_viewer')

  def testPost_InvalidJob(self):
    response = self.testapp.get('/results2/123', status=400)
    self.assertIn('Error', response.body)

  @mock.patch.object(
      results2, '_GetJobData', mock.MagicMock(return_value={'quests': []}))
  def testPost_JobHasNoTestQuest(self):
    response = self.testapp.get('/results2/123', status=400)
    self.assertIn('No Test quest', response.body)

