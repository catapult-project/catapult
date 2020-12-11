# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import shutil
import tempfile
from unittest import TestCase

from long_term_health import apk_finder
from long_term_health import full_milestone_info
from long_term_health import utils
import mock


class TestChromeVersion(TestCase):

  def testChromeVersionConstructUsingString(self):
    chrome_version = apk_finder.ChromeVersion('68.0.3440.64')
    self.assertEqual(68, chrome_version.milestone)
    self.assertEqual(0, chrome_version.minor)
    self.assertEqual(3440, chrome_version.build)
    self.assertEqual(64, chrome_version.patch)

  def testChromeVersionConstructUsingFourInts(self):
    chrome_version = apk_finder.ChromeVersion(68, 0, 3440, 64)
    self.assertEqual(68, chrome_version.milestone)
    self.assertEqual(0, chrome_version.minor)
    self.assertEqual(3440, chrome_version.build)
    self.assertEqual(64, chrome_version.patch)

  def testChromeVersionStringRepresentation(self):
    self.assertEqual('68.0.3440.64', str(
        apk_finder.ChromeVersion(68, 0, 3440, 64)))
    self.assertEqual('68.0.3440.64', str(
        apk_finder.ChromeVersion('68.0.3440.64')))

  def testChromeVersionDecrementVersionNormalUsage(self):
    chrome_version = apk_finder.ChromeVersion('68.0.3440.70')
    self.assertEqual('68.0.3440.64', str(
        chrome_version.GetDecrementedVersionNum(6)))
    self.assertEqual('68.0.3440.0', str(
        chrome_version.GetDecrementedVersionNum(70)))

  def testChromeVersionDecrementVersionIllegalUsage(self):
    chrome_version = apk_finder.ChromeVersion('68.0.3440.70')
    with self.assertRaises(AssertionError):
      chrome_version.GetDecrementedVersionNum(71)
    with self.assertRaises(AssertionError):
      chrome_version.GetDecrementedVersionNum(600)


class TestGetLatestAvailableVersionURI(TestCase):

  @mock.patch('subprocess.call')
  def testGetLatestAvailableVersionURI_foundImmediately(self, subprocess_call):
    subprocess_call.return_value = 0    # 0 means success.
    # It should use Monochrome if the version is 53 and above.
    self.assertEqual(
        'gs://chrome-signed/android-*/53.0.0.0/arm/MonochromeStable.apk',
        apk_finder.GetLatestAvailableVersionURI('53.0.0.0'))
    # It should use Chrome if the version is below 53.
    self.assertEqual(
        'gs://chrome-signed/android-*/52.0.0.0/arm/ChromeStable.apk',
        apk_finder.GetLatestAvailableVersionURI('52.0.0.0'))

  @mock.patch('subprocess.call')
  def testGetLatestAvailableVersionURI_foundWithThreeRetry(
      self, subprocess_call):
    subprocess_call.side_effect = [1, 1, 1, 0]  # 0 means success, 1 means fail.
    # It should use Monochrome if the version is 53 and above.
    self.assertEqual(
        'gs://chrome-signed/android-*/53.0.0.0/arm/MonochromeStable.apk',
        apk_finder.GetLatestAvailableVersionURI('53.0.0.3'))
    subprocess_call.side_effect = [1, 1, 1, 0]
    # It should use Chrome if the version is below 53.
    self.assertEqual(
        'gs://chrome-signed/android-*/52.0.0.0/arm/ChromeStable.apk',
        apk_finder.GetLatestAvailableVersionURI('52.0.0.3'))

  @mock.patch('subprocess.call')
  def testGetLatestAvailableVersionURI_failedToFind(self, subprocess_call):
    subprocess_call.return_value = 1    # 1 means fail.
    with self.assertRaises(AssertionError):
      apk_finder.GetLatestAvailableVersionURI('61.0.0.0')
    with self.assertRaises(utils.CloudDownloadFailed):
      apk_finder.GetLatestAvailableVersionURI('61.0.0.40')


class TestDownloadAPKFromURI(TestCase):

  @mock.patch('subprocess.call')
  def testDownloadAPKFromURI_success(self, subprocess_call):
    # Mock the download to be successful.
    subprocess_call.return_value = 0
    real_path = apk_finder.DownloadAPKFromURI(
        'gs://chrome-signed/android-*/56.0.0.3/arm/MonochromeStable.apk', 'out')
    self.assertEqual('out/56.0.0.3_arm_MonochromeStable.apk', real_path)

  @mock.patch('subprocess.call')
  def testDownloadAPKFromURI_failure(self, subprocess_call):
    # Mock the download to be unsuccessful.
    subprocess_call.return_value = 1
    with self.assertRaises(utils.CloudDownloadFailed):
      apk_finder.DownloadAPKFromURI('gs://chrome-signed/android-*/56.0.0.3/arm/'
                                    'MonochromeStable.apk', 'out')


class TestGetLocalAPK(TestCase):

  def setUp(self):
    self.dir = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.dir)

  def testGetLocalAPK_localAPKExists(self):
    _, apk_path = tempfile.mkstemp('.apk', '64.0.0.0_arm_Monochrome', self.dir)
    self.assertEqual(apk_path, apk_finder.GetLocalAPK(64, self.dir))

  def testGetLocalAPK_localAPKNotExists(self):
    self.assertIsNone(apk_finder.GetLocalAPK(64, self.dir))
    tempfile.mkstemp('.apk', '64.0.0.0_arm_Monochrome', self.dir)
    self.assertIsNone(apk_finder.GetLocalAPK(63, self.dir))


class TestGetAPK(TestCase):

  @mock.patch('long_term_health.apk_finder.GetLocalAPK')
  def testGetAPK_localApkExists(self, get_local_apk_function):
    get_local_apk_function.return_value = 'path_to_apk'
    self.assertEqual('path_to_apk', apk_finder.GetAPK(0, 'output_path', None))

  @mock.patch('long_term_health.apk_finder.GetLocalAPK')
  @mock.patch('long_term_health.apk_finder.DownloadAPKFromURI')
  @mock.patch('long_term_health.apk_finder.GetLatestAvailableVersionURI')
  @mock.patch('long_term_health.full_milestone_info.MilestoneInfo')
  def testGetAPK_localApkNotExists(
      self, milestone_info, get_latest_available_version_uri,
      download_apk_from_uri, get_local_apk):
    # mock the milestone_info instance method
    m_info_instance = milestone_info.return_value
    m_info_instance.GetVersionNumberFromMilestone.return_value = 'version_num'
    get_latest_available_version_uri.return_value = 'uri_to_apk'
    download_apk_from_uri.return_value = os.path.join(
        'output_path', 'path_to_apk')
    get_local_apk.return_value = None

    # create a faked `milestoneInfo` instance to be passed in
    mocked_m_info = full_milestone_info.MilestoneInfo(None)
    self.assertEqual(os.path.join('output_path', 'path_to_apk'),
                     apk_finder.GetAPK(0, 'output_path', mocked_m_info))
    get_latest_available_version_uri.assert_called_once_with('version_num')
    download_apk_from_uri.assert_called_once_with('uri_to_apk', 'output_path')




