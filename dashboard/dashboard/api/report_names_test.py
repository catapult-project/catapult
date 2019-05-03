# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import unittest

from dashboard.api import api_auth
from dashboard.api import report_names
from dashboard.common import testing_common
from dashboard.models import report_template


class ReportNamesTest(testing_common.TestCase):

  def setUp(self):
    super(ReportNamesTest, self).setUp()
    self.SetUpApp([('/api/report_names', report_names.ReportNamesHandler)])
    self.SetCurrentClientIdOAuth(api_auth.OAUTH_CLIENT_ID_WHITELIST[0])
    report_template.ReportTemplate(internal_only=False, name='external').put()
    report_template.ReportTemplate(internal_only=True, name='internal').put()

  def testInternal(self):
    self.SetCurrentUserOAuth(testing_common.INTERNAL_USER)
    response = json.loads(self.Post('/api/report_names').body)
    names = [d['name'] for d in response]
    self.assertIn('external', names)
    self.assertIn('internal', names)

  def testAnonymous(self):
    self.SetCurrentUserOAuth(None)
    response = json.loads(self.Post('/api/report_names').body)
    names = [d['name'] for d in response]
    self.assertIn('external', names)
    self.assertNotIn('internal', names)


if __name__ == '__main__':
  unittest.main()
