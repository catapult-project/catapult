# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import base64
import json
import mock

from dashboard.common import testing_common
from dashboard.services import milo_service

_BUILD_DETAILS = {
    'Master': 'chromium.perf',
    'blame': [
        'catapult-deps-roller@chromium.org',
        'sullivan@chromium.org',
    ],
    'builderName': 'Android Nexus6 Perf (3)',
    'currentStep': None,
    'eta': None,
    'finished': True,
    'internal': False,
    'number': 4712,
    'osFamily': 'Debian',
    'osVersion': '14.04',
    'properties': [
        [
            'branch',
            'master',
            'Build'
        ],
        [
            'buildbotURL',
            'http://build.chromium.org/p/chromium.perf/',
            'master.cfg'
        ],
        [
            'buildername',
            'Android Nexus6 Perf (3)',
            'Builder'
        ],
        [
            'buildnumber',
            4712,
            'Build'
        ],
        [
            'got_revision_cp',
            'refs/heads/master@{#442230}',
            'Annotation(bot_update)'
        ],
    ],
    'reason': 'scheduler',
    'results': 0,
    'slave': 'build45-b1',
    'steps': [
        {
            'eta': None,
            'expectations': [],
            'hidden': False,
            'isFinished': True,
            'isStarted': True,
            'logs': [
                [
                    'stdio',
                    'http://stdio'
                ],
                [
                    'json.output',
                    'http://json.output'
                ],
            ],
            'name': 'memory.top_10_mobile_stress',
            'results': [
                0,
                []
            ],
            'statistics': {},
            'step_number': 1,
        },
        {
            'eta': None,
            'expectations': [],
            'hidden': False,
            'isFinished': True,
            'isStarted': True,
            'logs': [
                [
                    'stdio',
                    'http://stdio'
                ],
                [
                    'json.output',
                    'http://json.output'
                ],
            ],
            'name': 'page_cycler.typical_25',
            'results': [
                0,
                []
            ],
            'statistics': {},
            'step_number': 2,
        },
        {
            'eta': None,
            'expectations': [],
            'hidden': False,
            'isFinished': True,
            'isStarted': True,
            'logs': [
                [
                    'stdio',
                    'http://stdio'
                ],
                [
                    'json.output',
                    'http://json.output'
                ],
            ],
            'name': 'sunspider',
            'results': [
                0,
                []
            ],
            'statistics': {},
            'step_number': 3,
        },
    ],
}


class MiloServiceTest(testing_common.TestCase):

  def _GenerateResponse(self, build_details):
    encoded_build_data = base64.b64encode(json.dumps(build_details))
    response_content = '12345%s' % json.dumps({'data': encoded_build_data})
    return testing_common.FakeResponseObject(200, response_content)

  def testGetBuildbotBuildInfo(self):
    mock_response = self._GenerateResponse(_BUILD_DETAILS)
    with mock.patch('google.appengine.api.urlfetch.fetch',
                    mock.MagicMock(
                        return_value=mock_response)):
      build_info = milo_service.GetBuildbotBuildInfo(
          'chromium.perf', 'Android Nexus6 Perf (3)', '4712')
      self.assertEqual('chromium.perf', build_info['Master'])


if __name__ == '__main__':
  unittest.main()
