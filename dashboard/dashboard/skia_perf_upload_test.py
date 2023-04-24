# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from flask import Flask
import json
import mock
import unittest
import webtest

from dashboard.api import api_auth
from dashboard import skia_perf_upload
from dashboard.common import testing_common

flask_app = Flask(__name__)


def SetInternalUserOAuth(mock_oauth):
  mock_oauth.get_current_user.return_value = testing_common.INTERNAL_USER
  mock_oauth.get_client_id.return_value = api_auth.OAUTH_CLIENT_ID_ALLOWLIST[0]


@flask_app.route('/skia_perf_upload', methods=['POST'])
def SkiaPerfUploadPost():
  return skia_perf_upload.SkiaPerfUploadPost()


class SkiaPerfUploadTest(testing_common.TestCase):

  def setUp(self):
    super().setUp()
    self.testapp = webtest.TestApp(flask_app)

  @mock.patch('dashboard.common.cloud_metric._PublishTSCloudMetric',
              mock.MagicMock())
  @mock.patch.object(skia_perf_upload, 'cloudstorage')
  def testUploadRowInternal(self, mock_gcs):
    testing_common.AddTests(['ChromiumAndroid'], ['android-cronet-arm-rel'], {
        'resource_sizes (CronetSample.apk)': {
            'InstallSize': {
                'APK size': {}
            }
        }
    })

    row_params = {
        'internal_only': True,
        'a_build_uri': '[Build Status](https://xxx)',
        'a_stdio_uri': '[Buildbot stdio](http://xxx)',
        'd_count': 1,
        'd_max': 2424228,
        'd_min': 2424228,
        'd_sum': 2424228,
        'd_std': None,
        'r_commit_pos': 668729,
        'r_v8_rev': '0027447130c41b7724f4babf2d3f340a963b5e42',
        'r_webrtc_git': 'a7acc4dd8d303310fb1bd2cfafbc032f308b1fbc',
        'value': 2424228
    }

    rows = testing_common.AddRows(
        ('ChromiumAndroid/android-cronet-arm-rel/'
         'resource_sizes (CronetSample.apk)/InstallSize/APK size'),
        {668729: row_params})

    skia_data_expected = {
        'version': 1,
        'git_hash': 'CP:668729',
        'key': {
            'master': 'ChromiumAndroid',
            'bot': 'android-cronet-arm-rel',
            'benchmark': 'resource_sizes (CronetSample.apk)'
        },
        'results': [{
            'measurements': {
                'stat': [{
                    'value': 'value',
                    'measurement': 2424228.0
                }, {
                    'value': 'count',
                    'measurement': 1
                }, {
                    'value': 'max',
                    'measurement': 2424228
                }, {
                    'value': 'min',
                    'measurement': 2424228
                }, {
                    'value': 'sum',
                    'measurement': 2424228
                }]
            },
            'key': {
                'improvement_direction': 'unknown',
                'test': 'InstallSize',
                'subtest_1': 'APK size',
            }
        }],
        'links': {
            'Build Page':
                '[Build Status](https://xxx)',
            'Test stdio':
                '[Buildbot stdio](http://xxx)',
            'Chromium Commit Position':
                'https://crrev.com/668729',
            'V8 Git Hash': ('https://chromium.googlesource.com/v8/v8/+/'
                            '0027447130c41b7724f4babf2d3f340a963b5e42'),
            'WebRTC Git Hash':
                'https://webrtc.googlesource.com/src/+/a7acc4dd8d303310fb1bd2cfafbc032f308b1fbc'
        }
    }

    params = {'rows': [row.key.urlsafe().decode() for row in rows]}

    self.testapp.post('/skia_perf_upload', json.dumps(params))

    self.assertEqual(len(mock_gcs.mock_calls), 4)

    init_call = mock_gcs.mock_calls[1]
    write_call = mock_gcs.mock_calls[2]

    mock_args, mock_kwargs = init_call.args, init_call.kwargs

    self.assertTrue(mock_args[0].startswith('/chrome-perf-public/'))
    self.assertTrue((
        'ChromiumAndroid/android-cronet-arm-rel/resource_sizes (CronetSample.apk)/'
        'InstallSize/APK size/668729/') in mock_args[0])
    self.assertEqual(mock_args[1], 'w')
    self.assertEqual(mock_kwargs['content_type'], 'application/json')

    write_call.assert_called_once()

    mock_args = write_call.args
    self.assertEqual(json.loads(mock_args[0]), skia_data_expected)


if __name__ == "__main__":
  unittest.main()
