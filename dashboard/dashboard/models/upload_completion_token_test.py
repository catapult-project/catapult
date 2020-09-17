# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import datetime
import time
import unittest
import uuid

from dashboard.common import testing_common
from dashboard.models import upload_completion_token


class UploadCompletionTokenTest(testing_common.TestCase):

  def setUp(self):
    super(UploadCompletionTokenTest, self).setUp()
    testing_common.SetIsInternalUser('foo@bar.com', True)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def testPutAndUpdate(self):
    token_id = str(uuid.uuid4())
    gcs_file = 'path/%s.gcs' % str(uuid.uuid4())
    token = upload_completion_token.Token(
        id=token_id, temporary_staging_file_path=gcs_file).put().get()

    self.assertEqual(token_id, token.key.id())
    self.assertEqual(gcs_file, token.temporary_staging_file_path)
    self.assertEqual(token.state, upload_completion_token.State.PENDING)

    # Sleep for 1 second, so update_time change is visible.
    sleep_time = datetime.timedelta(seconds=1)
    time.sleep(sleep_time.total_seconds())

    new_state = upload_completion_token.State.PROCESSING
    token.UpdateStateAsync(new_state).wait()

    changed_token = upload_completion_token.Token.get_by_id(token_id)
    self.assertEqual(token_id, changed_token.key.id())
    self.assertEqual(gcs_file, changed_token.temporary_staging_file_path)
    self.assertTrue(
        (changed_token.update_time - changed_token.creation_time) >= sleep_time)
    self.assertEqual(changed_token.state, new_state)

    new_state = upload_completion_token.State.COMPLETED
    changed_token.UpdateStateAsync(new_state).wait()

    changed_token = upload_completion_token.Token.get_by_id(token_id)
    self.assertEqual(changed_token.state, new_state)

  def testStatusUpdateWithMeasurements(self):
    token = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    self.assertEqual(token.state, upload_completion_token.State.PENDING)

    measurement1, measurement2 = token.PopulateMeasurements({
        'test/1': True,
        'test/2': False
    })
    self.assertEqual(token.state, upload_completion_token.State.PROCESSING)

    token.UpdateStateAsync(upload_completion_token.State.PROCESSING).wait()
    self.assertEqual(token.state, upload_completion_token.State.PROCESSING)

    measurement1.state = upload_completion_token.State.FAILED
    measurement1.put()
    self.assertEqual(token.state, upload_completion_token.State.PROCESSING)

    token.UpdateStateAsync(upload_completion_token.State.COMPLETED).wait()
    measurement2.state = upload_completion_token.State.COMPLETED
    measurement2.put()
    self.assertEqual(token.state, upload_completion_token.State.FAILED)

    measurement1.state = upload_completion_token.State.COMPLETED
    measurement1.put()
    self.assertEqual(token.state, upload_completion_token.State.COMPLETED)

  def testStatusUpdateWithExpiredMeasurement(self):
    token = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    measurement1, measurement2 = token.PopulateMeasurements({
        'test/1': True,
        'test/2': False
    })

    measurement1.key.delete()

    self.assertEqual(token.state, upload_completion_token.State.PROCESSING)

    token.UpdateStateAsync(upload_completion_token.State.COMPLETED).wait()
    self.assertEqual(token.state, upload_completion_token.State.PROCESSING)

    measurement2.state = upload_completion_token.State.COMPLETED
    measurement2.put()
    self.assertEqual(token.state, upload_completion_token.State.COMPLETED)

  @unittest.expectedFailure
  def testPopulateMeasurementsMultipleTimes(self):
    token = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    token.PopulateMeasurements({'test/1': True, 'test/2': False})
    token.PopulateMeasurements({'test/3': False, 'test/4': False})

  def testCreateSameMeasurementsForDifferentTokens(self):
    test_path = 'test/path'
    token1 = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    token1.PopulateMeasurements({test_path: True})

    token2 = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    token2.PopulateMeasurements({test_path: True})

    measurement1 = upload_completion_token.Measurement.get_by_id(
        test_path, parent=token1.key)
    measurement2 = upload_completion_token.Measurement.get_by_id(
        test_path, parent=token2.key)

    self.assertNotEqual(measurement1, measurement2)

  def testUpdateObjectStateAsync(self):
    target_state = upload_completion_token.State.COMPLETED

    upload_completion_token.Token.UpdateObjectStateAsync(None,
                                                         target_state).wait()

    token = upload_completion_token.Token(id=str(uuid.uuid4())).put().get()
    upload_completion_token.Token.UpdateObjectStateAsync(token,
                                                         target_state).wait()
    self.assertEqual(token.state, target_state)

  def testMeasurementUpdateStateByIdAsync(self):
    test_path = 'test/path'
    token_id = str(uuid.uuid4())
    target_state = upload_completion_token.State.COMPLETED
    token_key = upload_completion_token.Token(id=token_id).put()
    upload_completion_token.Measurement(id=test_path, parent=token_key).put()

    upload_completion_token.Measurement.UpdateStateByIdAsync(
        None, token_id, target_state).wait()
    upload_completion_token.Measurement.UpdateStateByIdAsync(
        test_path, None, target_state).wait()
    upload_completion_token.Measurement.UpdateStateByIdAsync(
        'expired', token_id, target_state).wait()

    measurement = upload_completion_token.Measurement.get_by_id(
        test_path, parent=token_key)
    self.assertNotEqual(measurement.state, target_state)

    upload_completion_token.Measurement.UpdateStateByIdAsync(
        test_path, token_id, target_state).wait()

    measurement = upload_completion_token.Measurement.get_by_id(
        test_path, parent=token_key)
    self.assertEqual(measurement.state, target_state)


if __name__ == '__main__':
  unittest.main()
