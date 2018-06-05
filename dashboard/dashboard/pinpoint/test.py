# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.common import namespaced_stored_object
from dashboard.common import testing_common


CATAPULT_URL = 'https://chromium.googlesource.com/catapult'
CHROMIUM_URL = 'https://chromium.googlesource.com/chromium/src'


class TestCase(testing_common.TestCase):

  def setUp(self):
    super(TestCase, self).setUp()

    self.SetCurrentUser('internal@chromium.org', is_admin=True)

    namespaced_stored_object.Set('repositories', {
        'catapult': {'repository_url': CATAPULT_URL},
        'chromium': {'repository_url': CHROMIUM_URL},
        'another_repo': {'repository_url': 'https://another/url'},
    })
    namespaced_stored_object.Set('repository_urls_to_names', {
        CATAPULT_URL: 'catapult',
        CHROMIUM_URL: 'chromium',
    })
