#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Unit tests for the contents of shared_prefs.py (mostly SharedPrefs).
"""

import logging
import unittest

from unittest import mock

from devil.android import device_utils
from devil.android.sdk import shared_prefs
from devil.android.sdk import version_codes

INITIAL_XML = ("<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n"
               '<map>\n'
               '  <int name="databaseVersion" value="107" />\n'
               '  <boolean name="featureEnabled" value="false" />\n'
               '  <string name="someHashValue">249b3e5af13d4db2</string>\n'
               '</map>')


def MockDeviceWithFiles(files=None):
  if files is None:
    files = {}

  def path_exists(path, **_kwargs):
    return path in files

  def write_file(path, contents, **_kwargs):
    files[path] = contents

  def read_file(path, **_kwargs):
    return files[path]

  device = mock.MagicMock(spec=device_utils.DeviceUtils)
  device.PathExists = mock.Mock(side_effect=path_exists)
  device.WriteFile = mock.Mock(side_effect=write_file)
  device.ReadFile = mock.Mock(side_effect=read_file)
  return device


class SharedPrefsTest(unittest.TestCase):
  def setUp(self):
    self.device = MockDeviceWithFiles({
        '/data/data/com.some.package/shared_prefs/prefs.xml': INITIAL_XML
    })
    self.expected_data = {
        'databaseVersion': 107,
        'featureEnabled': False,
        'someHashValue': '249b3e5af13d4db2'
    }

  def testPropertyLifetime(self):
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'prefs.xml')
    self.assertEqual(len(prefs), 0)  # collection is empty before loading
    prefs.SetInt('myValue', 444)
    self.assertEqual(len(prefs), 1)
    self.assertEqual(prefs.GetInt('myValue'), 444)
    self.assertTrue(prefs.HasProperty('myValue'))
    prefs.Remove('myValue')
    self.assertEqual(len(prefs), 0)
    self.assertFalse(prefs.HasProperty('myValue'))
    with self.assertRaises(KeyError):
      prefs.GetInt('myValue')

  def testPropertyType(self):
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'prefs.xml')
    prefs.SetInt('myValue', 444)
    self.assertEqual(prefs.PropertyType('myValue'), 'int')
    with self.assertRaises(TypeError):
      prefs.GetString('myValue')
    with self.assertRaises(TypeError):
      prefs.SetString('myValue', 'hello')

  def testLoad(self):
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'prefs.xml')
    self.assertEqual(len(prefs), 0)  # collection is empty before loading
    prefs.Load()
    self.assertEqual(len(prefs), len(self.expected_data))
    self.assertEqual(prefs.AsDict(), self.expected_data)
    self.assertFalse(prefs.changed)

  def testClear(self):
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'prefs.xml')
    prefs.Load()
    self.assertEqual(prefs.AsDict(), self.expected_data)
    self.assertFalse(prefs.changed)
    prefs.Clear()
    self.assertEqual(len(prefs), 0)  # collection is empty now
    self.assertTrue(prefs.changed)

  def testCommit(self):
    type(self.device).build_version_sdk = mock.PropertyMock(
        return_value=version_codes.LOLLIPOP_MR1)
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'other_prefs.xml')
    self.assertFalse(self.device.PathExists(prefs.path))  # file does not exist
    prefs.Load()
    self.assertEqual(len(prefs), 0)  # file did not exist, collection is empty
    prefs.SetInt('magicNumber', 42)
    prefs.SetFloat('myMetric', 3.14)
    prefs.SetLong('bigNumner', 6000000000)
    prefs.SetStringSet('apps', ['gmail', 'chrome', 'music'])
    self.assertFalse(self.device.PathExists(prefs.path))  # still does not exist
    self.assertTrue(prefs.changed)
    prefs.Commit()
    self.assertTrue(self.device.PathExists(prefs.path))  # should exist now
    self.device.KillAll.assert_called_once_with(
        prefs.package, exact=True, as_root=True, quiet=True)
    self.assertFalse(prefs.changed)

    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'other_prefs.xml')
    self.assertEqual(len(prefs), 0)  # collection is empty before loading
    prefs.Load()
    self.assertEqual(
        prefs.AsDict(), {
            'magicNumber': 42,
            'myMetric': 3.14,
            'bigNumner': 6000000000,
            'apps': ['gmail', 'chrome', 'music']
        })  # data survived roundtrip

  def testForceCommit(self):
    type(self.device).build_version_sdk = mock.PropertyMock(
        return_value=version_codes.LOLLIPOP_MR1)
    prefs = shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                     'prefs.xml')
    prefs.Load()
    new_xml = 'Not valid XML'
    self.device.WriteFile('/data/data/com.some.package/shared_prefs/prefs.xml',
                          new_xml)
    prefs.Commit()
    # Since we didn't change anything, Commit() should be a no-op.
    self.assertEqual(
        self.device.ReadFile(
            '/data/data/com.some.package/shared_prefs/prefs.xml'), new_xml)
    prefs.Commit(force_commit=True)
    # Forcing the commit should restore the originally read XML.
    self.assertEqual(
        self.device.ReadFile(
            '/data/data/com.some.package/shared_prefs/prefs.xml'), INITIAL_XML)

  def testAsContextManager_onlyReads(self):
    with shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                  'prefs.xml') as prefs:
      self.assertEqual(prefs.AsDict(), self.expected_data)  # loaded and ready
    self.assertEqual(self.device.WriteFile.call_args_list, [])  # did not write

  def testAsContextManager_readAndWrite(self):
    type(self.device).build_version_sdk = mock.PropertyMock(
        return_value=version_codes.LOLLIPOP_MR1)
    with shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                  'prefs.xml') as prefs:
      prefs.SetBoolean('featureEnabled', True)
      prefs.Remove('someHashValue')
      prefs.SetString('newString', 'hello')

    self.assertTrue(self.device.WriteFile.called)  # did write
    with shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                  'prefs.xml') as prefs:
      # changes persisted
      self.assertTrue(prefs.GetBoolean('featureEnabled'))
      self.assertFalse(prefs.HasProperty('someHashValue'))
      self.assertEqual(prefs.GetString('newString'), 'hello')
      self.assertTrue(prefs.HasProperty('databaseVersion'))  # still there

  def testAsContextManager_commitAborted(self):
    with self.assertRaises(TypeError):
      with shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                    'prefs.xml') as prefs:
        prefs.SetBoolean('featureEnabled', True)
        prefs.Remove('someHashValue')
        prefs.SetString('newString', 'hello')
        prefs.SetInt('newString', 123)  # oops!

    self.assertEqual(self.device.WriteFile.call_args_list, [])  # did not write
    with shared_prefs.SharedPrefs(self.device, 'com.some.package',
                                  'prefs.xml') as prefs:
      # contents were not modified
      self.assertEqual(prefs.AsDict(), self.expected_data)

  def testEncryptedPath(self):
    type(self.device).build_version_sdk = mock.PropertyMock(
        return_value=version_codes.MARSHMALLOW)
    with shared_prefs.SharedPrefs(
        self.device, 'com.some.package', 'prefs.xml',
        use_encrypted_path=True) as prefs:
      self.assertTrue(prefs.path.startswith('/data/data'))

    type(self.device).build_version_sdk = mock.PropertyMock(
        return_value=version_codes.NOUGAT)
    with shared_prefs.SharedPrefs(
        self.device, 'com.some.package', 'prefs.xml',
        use_encrypted_path=True) as prefs:
      self.assertTrue(prefs.path.startswith('/data/user_de/0'))


if __name__ == '__main__':
  logging.getLogger().setLevel(logging.DEBUG)
  unittest.main(verbosity=2)
