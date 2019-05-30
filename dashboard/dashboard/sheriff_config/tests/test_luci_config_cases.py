# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Tests for the luci_config client."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from googleapiclient.http import HttpMockSequence
import unittest
import luci_config


class LuciConfigTest(unittest.TestCase):

  # TODO(dberris): Implement more tests as we gather more use-cases.
  def testFindingAllSheriffConfigs(self):
    with open('tests/config-discovery.json') as discovery_file:
      discovery_response = discovery_file.read()
    with open('tests/configs-projects-empty.json') as configs_get_projects_file:
      configs_get_projects_response = configs_get_projects_file.read()
    http = HttpMockSequence([({
        'status': '200'
    }, discovery_response), ({
        'status': '200'
    }, configs_get_projects_response)])
    service = luci_config.CreateConfigClient(http=http)
    self.assertEqual({}, luci_config.FindAllSheriffConfigs(service))

  def testFailingCreateConfigClient(self):
    with self.assertRaisesRegex(luci_config.DiscoveryError,
                                'Service discovery failed:'):
      http = HttpMockSequence([({'status': '403'}, 'Forbidden')])
      _ = luci_config.CreateConfigClient(http)
