# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import sys
import unittest

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common
from dashboard.pinpoint import test


@unittest.skipIf(sys.version_info.major == 3,
                   'Skipping old handler tests for python 3.')
class ConfigTest(test.TestCase):

  def setUp(self):
    # TODO(https://crbug.com/1262292): Change to super() after Python2 trybots retire.
    # pylint: disable=super-with-arguments
    super(ConfigTest, self).setUp()

    self.SetCurrentUser('external@chromium.org')

    namespaced_stored_object.Set('bot_configurations', {
        'chromium-rel-mac11-pro': {},
    })

    self.SetCurrentUser('internal@chromium.org', is_admin=True)
    testing_common.SetIsInternalUser('internal@chromium.org', True)

    namespaced_stored_object.Set('bot_configurations', {
        'internal-only-bot': {},
    })

  def testGet_External(self):
    self.SetCurrentUser('external@chromium.org')

    actual = json.loads(self.testapp.post('/api/config').body)
    expected = {
        'configurations': ['chromium-rel-mac11-pro'],
    }
    self.assertEqual(actual, expected)

  def testGet_Internal(self):
    self.SetCurrentUser('internal@chromium.org')

    actual = json.loads(self.testapp.post('/api/config').body)
    expected = {
        'configurations': ['internal-only-bot'],
    }
    self.assertEqual(actual, expected)
