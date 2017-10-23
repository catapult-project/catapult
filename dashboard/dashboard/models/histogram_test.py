# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import sys

from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import histogram
from tracing.value.diagnostics import reserved_infos


class SparseDiagnosticTest(testing_common.TestCase):
  """Test case for functions in SparseDiagnostic."""

  def setUp(self):
    super(SparseDiagnosticTest, self).setUp()
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testGetMostRecentValuesByNames_ReturnAllData(self):
    data_samples = [
        {
            'type': 'GenericSet',
            'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb826',
            'values': ['alice@chromium.org']
        },
        {
            'type': 'GenericSet',
            'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb827',
            'values': ['abc']
        }]

    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_samples[0]), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_samples[0]['guid'],
        name=reserved_infos.OWNERS.name)
    entity.put()

    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_samples[1]), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_samples[1]['guid'],
        name=reserved_infos.BUG_COMPONENTS.name)
    entity.put()

    lookup_result = histogram.SparseDiagnostic.GetMostRecentValuesByNames(
        test_key, set([reserved_infos.OWNERS.name,
                       reserved_infos.BUG_COMPONENTS.name]))

    self.assertEqual(lookup_result.get(reserved_infos.OWNERS.name),
                     ['alice@chromium.org'])
    self.assertEqual(lookup_result.get(reserved_infos.BUG_COMPONENTS.name),
                     ['abc'])

  def testGetMostRecentValuesByNames_ReturnsNoneIfNoneFound(self):
    data_sample = {
        'type': 'GenericSet',
        'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb826',
        'values': ['alice@chromium.org']
    }

    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_sample), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_sample['guid'],
        name=reserved_infos.OWNERS.name)
    entity.put()

    lookup_result = histogram.SparseDiagnostic.GetMostRecentValuesByNames(
        test_key, set([reserved_infos.OWNERS.name,
                       reserved_infos.BUG_COMPONENTS.name]))


    self.assertEqual(lookup_result.get(reserved_infos.OWNERS.name),
                     ['alice@chromium.org'])
    self.assertIsNone(lookup_result.get(reserved_infos.BUG_COMPONENTS.name))

  def testGetMostRecentValuesByNames_ReturnsNoneIfNoName(self):
    data_sample = {
        'guid': 'abc',
        'osName': 'linux',
        'type': 'DeviceInfo'
    }

    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_sample), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_sample['guid'])
    entity.put()

    lookup_result = histogram.SparseDiagnostic.GetMostRecentValuesByNames(
        test_key, set([reserved_infos.OWNERS.name,
                       reserved_infos.BUG_COMPONENTS.name]))

    self.assertIsNone(lookup_result.get(reserved_infos.OWNERS.name))
    self.assertIsNone(lookup_result.get(reserved_infos.BUG_COMPONENTS.name))

  def testGetMostRecentValuesByNames_RaisesErrorIfDuplicateName(self):
    data_samples = [
        {
            'type': 'GenericSet',
            'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb826',
            'values': ['alice@chromium.org']
        },
        {
            'type': 'GenericSet',
            'guid': 'eb212e80-db58-4cbd-b331-c2245ecbb827',
            'values': ['bob@chromium.org']
        }]

    test_key = utils.TestKey('Chromium/win7/foo')
    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_samples[0]), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_samples[0]['guid'],
        name=reserved_infos.OWNERS.name)
    entity.put()

    entity = histogram.SparseDiagnostic(
        data=json.dumps(data_samples[1]), test=test_key, start_revision=1,
        end_revision=sys.maxint, id=data_samples[1]['guid'],
        name=reserved_infos.OWNERS.name)
    entity.put()

    self.assertRaises(
        AssertionError,
        histogram.SparseDiagnostic.GetMostRecentValuesByNames,
        test_key,
        set([reserved_infos.OWNERS.name, reserved_infos.BUG_COMPONENTS.name]))
