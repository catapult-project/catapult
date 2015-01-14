# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.core.backends import android_command_line_backend


class AndroidCommandLineBackendTest(unittest.TestCase):

  def testQuoteIfNeededNoEquals(self):
    string = 'value'
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeededNoSpaces(self):
    string = 'key=valueA'
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeededAlreadyQuoted(self):
    string = "key='valueA valueB'"
    self.assertEqual(string,
                     android_command_line_backend._QuoteIfNeeded(string))

  def testQuoteIfNeeded(self):
    string = 'key=valueA valueB'
    expected_output = "key='valueA valueB'"
    self.assertEqual(expected_output,
                     android_command_line_backend._QuoteIfNeeded(string))
