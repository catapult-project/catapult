# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from argparse import ArgumentTypeError
from datetime import datetime
from unittest import TestCase

from long_term_health import utils
import mock


class TestParseIsoFormatDate(TestCase):

  def testParseIsoFormatDate(self):
    self.assertEqual(datetime(2018, 8, 5, 1, 22, 39),
                     utils.ParseIsoFormatDate('2018-08-05T01:22:39'))


class TestParseDate(TestCase):

  def testParseDate_normalUsage(self):
    self.assertEqual(datetime(2018, 8, 5), utils.ParseDate('2018-08-05'))
    self.assertEqual(datetime(2018, 8, 5), utils.ParseDate('2018-8-05'))

  def testParseDate_illegalUsage(self):
    with self.assertRaises(ArgumentTypeError):
      utils.ParseDate('2018--8-05')
      utils.ParseDate('2018--8--05')
      utils.ParseDate('2018.08.05')
      utils.ParseDate('2018/08/05')


class TestIsGsutilInstalled(TestCase):

  @mock.patch('subprocess.call')
  def testIsGsutilInstalled_installed(self, subprocess_call_function):
    subprocess_call_function.return_value = 0
    self.assertTrue(utils.IsGsutilInstalled())

  @mock.patch('subprocess.call')
  def testIsGsutilInstalled_notInstalled(self, subprocess_call_function):
    subprocess_call_function.return_value = 1
    self.assertFalse(utils.IsGsutilInstalled())


class TestColoredStr(TestCase):

  def testColoredStr(self):
    self.assertEqual('\033[92mstring\033[0m', utils.ColoredStr('string'))
