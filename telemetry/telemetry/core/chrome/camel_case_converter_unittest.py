# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.core.chrome import camel_case_converter

class TestCamelCaseConverter(unittest.TestCase):
  def testFromCamelCase(self):
    camel_case_data = {
      'gpu': {
        'vendorId': 1000,
        'deviceId': 2000,
        'vendorString': 'aString',
        'deviceString': 'bString' },
      'secondaryGpus': [
        { 'vendorId': 3000, 'deviceId': 4000,
          'vendorString': 'k', 'deviceString': 'l' }
      ]
    }
    underscore_data = {
      'gpu': {
        'vendor_id': 1000,
        'device_id': 2000,
        'vendor_string': 'aString',
        'device_string': 'bString' },
      'secondary_gpus': [
        { 'vendor_id': 3000, 'device_id': 4000,
          'vendor_string': 'k', 'device_string': 'l' }
      ]
    }
    self.assertEquals(
        camel_case_converter.CamelCaseConverter.FromCamelCase(camel_case_data),
        underscore_data)
