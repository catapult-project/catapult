# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import base64
import json
import logging
import sys

from dashboard.pinpoint import test


class TaskUpdatesTest(test.TestCase):

  def setUp(self):
    # Intercept the logging messages, so that we can see them when we have test
    # output in failures.
    self.logger = logging.getLogger()
    self.logger.level = logging.DEBUG
    self.stream_handler = logging.StreamHandler(sys.stdout)
    self.logger.addHandler(self.stream_handler)
    self.addCleanup(self.logger.removeHandler, self.stream_handler)
    super(TaskUpdatesTest, self).setUp()

  def testPostWorks(self):
    self.Post(
        '/_ah/push-handlers/task-updates',
        json.dumps({
            'message': {
                'attributes': {
                    'key': 'value'
                }
            },
            'data':
                base64.standard_b64encode(
                    json.dumps({
                        'job_id': 'cafef00d',
                        'task': {
                            'id': 1,
                            'type': 'build',
                        },
                    })),
        }),
        status=204)

  def testPostInvalidData(self):
    self.Post(
        '/_ah/push-handlers/task-updates',
        json.dumps({
            'message': {
                'attributes': {
                    'nothing': 'important'
                }
            },
            'data': '{"not": "base64-encoded"}',
        }),
        status=204)
    self.Post(
        '/_ah/push-handlers/task-updates',
        json.dumps({
            'message': {
                'attributes': {
                    'nothing': 'important'
                }
            },
            'data': base64.standard_b64encode('not json formatted'),
        }),
        status=204)
