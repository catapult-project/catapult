# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import os
import shutil
import tempfile
import unittest

from py_utils import cloud_storage  # pylint: disable=import-error

from telemetry.page import page
from telemetry.testing import system_stub
from telemetry.wpr import archive_info


class MockPage(page.Page):
  def __init__(self, url, name=None):
    super(MockPage, self).__init__(url, None, name=name)


page1 = MockPage('http://www.foo.com/', 'Foo')
page2 = MockPage('http://www.bar.com/', 'Bar')
page3 = MockPage('http://www.baz.com/')
recording1 = 'data_001.wpr'
recording2 = 'data_002.wpr'
archive_info_contents = ("""
{
"archives": {
  "%s": ["%s", "%s"],
  "%s": ["%s"]
}
}
""" % (recording1, page1.display_name, page2.display_name, recording2,
       page3.display_name))


class WprArchiveInfoTest(unittest.TestCase):
  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    # Write the metadata.
    self.story_set_archive_info_file = os.path.join(
        self.tmp_dir, 'info.json')
    with open(self.story_set_archive_info_file, 'w') as f:
      f.write(archive_info_contents)

    # Write the existing .wpr files.
    for i in [1, 2]:
      with open(os.path.join(self.tmp_dir, ('data_00%d.wpr' % i)), 'w') as f:
        f.write(archive_info_contents)

    # Create the PageSetArchiveInfo object to be tested.
    self.archive_info = archive_info.WprArchiveInfo.FromFile(
        self.story_set_archive_info_file, cloud_storage.PUBLIC_BUCKET)
    # Use cloud_storage system stub.
    self.overrides = system_stub.Override(archive_info, ['cloud_storage'])

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)
    self.overrides.Restore()

  def assertCorrectHashFile(self, file_path):
    old_ch = cloud_storage.CalculateHash
    cloud_storage.CalculateHash = self.overrides.cloud_storage.CalculateHash
    try:
      self.assertTrue(os.path.exists(file_path + '.sha1'))
      with open(file_path + '.sha1', 'rb') as f:
        self.assertEquals(cloud_storage.CalculateHash(file_path), f.read())
    finally:
      cloud_storage.CalculateHash = old_ch

  def testDownloadArchivesIfNeeded(self):
    cloud_storage_stub = self.overrides.cloud_storage
    # Second hash doesn't match, need to fetch it.
    cloud_storage_stub.SetRemotePathsForTesting(
        {cloud_storage.PUBLIC_BUCKET: {recording1: "dummyhash",
                                       recording2: "dummyhash22"}})
    cloud_storage_stub.SetCalculatedHashesForTesting(
        {os.path.join(self.tmp_dir, recording1): "dummyhash",
         os.path.join(self.tmp_dir, recording2): "dummyhash2",})
    self.archive_info.DownloadArchivesIfNeeded()
    self.assertEquals(len(cloud_storage_stub.downloaded_files), 1)
    self.assertEquals(cloud_storage_stub.downloaded_files[0], recording2)

  def testReadingArchiveInfo(self):
    self.assertIsNotNone(self.archive_info.WprFilePathForStory(page1))
    self.assertEquals(recording1, os.path.basename(
        self.archive_info.WprFilePathForStory(page1)))

    self.assertIsNotNone(self.archive_info.WprFilePathForStory(page2))
    self.assertEquals(recording1, os.path.basename(
        self.archive_info.WprFilePathForStory(page2)))

    self.assertIsNotNone(self.archive_info.WprFilePathForStory(page3))
    self.assertEquals(recording2, os.path.basename(
        self.archive_info.WprFilePathForStory(page3)))

  def testArchiveInfoFileGetsUpdated(self):
    """Ensures that the archive info file is updated correctly."""

    expected_archive_file_contents = {
        u'description': (u'Describes the Web Page Replay archives for a'
                         u' story set. Don\'t edit by hand! Use record_wpr for'
                         u' updating.'),
        u'archives': {
            u'data_003.wpr': [u'Bar', u'http://www.baz.com/'],
            u'data_001.wpr': [u'Foo']
        }
    }

    new_temp_recording = os.path.join(self.tmp_dir, 'recording.wpr')
    expected_archive_file_path = os.path.join(self.tmp_dir, 'data_003.wpr')
    hash_dictionary = {expected_archive_file_path:'filehash'}
    cloud_storage_stub = self.overrides.cloud_storage
    cloud_storage_stub.SetCalculatedHashesForTesting(hash_dictionary)
    with open(new_temp_recording, 'w') as f:
      f.write('wpr data')
    self.archive_info.AddNewTemporaryRecording(new_temp_recording)
    self.archive_info.AddRecordedStories([page2, page3])

    with open(self.story_set_archive_info_file, 'r') as f:
      archive_file_contents = json.load(f)
      self.assertEquals(expected_archive_file_contents, archive_file_contents)

    # Nit: Ensure the saved json does not contian trailing spaces.
    with open(self.story_set_archive_info_file, 'rU') as f:
      for line in f:
        self.assertFalse(line.rstrip('\n').endswith(' '))

  def testModifications(self):
    recording1_path = os.path.join(self.tmp_dir, recording1)
    recording2_path = os.path.join(self.tmp_dir, recording2)

    new_recording1 = os.path.join(self.tmp_dir, 'data_003.wpr')
    new_recording2 = os.path.join(self.tmp_dir, 'data_004.wpr')
    hash_dictionary = {new_recording1:'file_hash1',
                       new_recording2:'file_hash2'}
    cloud_storage_stub = self.overrides.cloud_storage
    cloud_storage_stub.SetCalculatedHashesForTesting(hash_dictionary)

    new_temp_recording = os.path.join(self.tmp_dir, 'recording.wpr')
    with open(new_temp_recording, 'w') as f:
      f.write('wpr data')

    self.archive_info.AddNewTemporaryRecording(new_temp_recording)

    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForStory(page1))
    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForStory(page2))
    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForStory(page3))

    self.archive_info.AddRecordedStories([page2])

    self.assertTrue(os.path.exists(new_recording1))
    self.assertFalse(os.path.exists(new_temp_recording))

    self.assertTrue(os.path.exists(recording1_path))
    self.assertTrue(os.path.exists(recording2_path))
    self.assertCorrectHashFile(new_recording1)

    with open(new_temp_recording, 'w') as f:
      f.write('wpr data')

    self.archive_info.AddNewTemporaryRecording(new_temp_recording)
    self.archive_info.AddRecordedStories([page3])

    self.assertTrue(os.path.exists(new_recording2))
    self.assertCorrectHashFile(new_recording2)
    self.assertFalse(os.path.exists(new_temp_recording))

    self.assertTrue(os.path.exists(recording1_path))
    # recording2 is no longer needed, so it was deleted.
    self.assertFalse(os.path.exists(recording2_path))

  def testCreatingNewArchiveInfo(self):
    # Write only the page set without the corresponding metadata file.
    story_set_contents = ("""
    {
        archive_data_file": "new_archive_info.json",
        "pages": [
            {
                "url": "%s",
            }
        ]
    }""" % page1.url)

    story_set_file = os.path.join(self.tmp_dir, 'new_story_set.json')
    with open(story_set_file, 'w') as f:
      f.write(story_set_contents)

    self.story_set_archive_info_file = os.path.join(self.tmp_dir,
                                                   'new_archive_info.json')

    expected_archive_file_path = os.path.join(self.tmp_dir,
                                              'new_archive_info_000.wpr')
    hash_dictionary = {expected_archive_file_path:'filehash'}
    self.overrides.cloud_storage.SetCalculatedHashesForTesting(hash_dictionary)

    # Create the WprArchiveInfo object to be tested.
    self.archive_info = archive_info.WprArchiveInfo.FromFile(
        self.story_set_archive_info_file, cloud_storage.PUBLIC_BUCKET)

    # Add a recording for all the pages.
    new_temp_recording = os.path.join(self.tmp_dir, 'recording.wpr')
    with open(new_temp_recording, 'w') as f:
      f.write('wpr data')

    self.archive_info.AddNewTemporaryRecording(new_temp_recording)

    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForStory(page1))

    self.archive_info.AddRecordedStories([page1])

    # Expected name for the recording (decided by WprArchiveInfo).
    new_recording = os.path.join(self.tmp_dir, 'new_archive_info_000.wpr')

    self.assertTrue(os.path.exists(new_recording))
    self.assertFalse(os.path.exists(new_temp_recording))
    self.assertCorrectHashFile(new_recording)

    # Check that the archive info was written correctly.
    self.assertTrue(os.path.exists(self.story_set_archive_info_file))
    read_archive_info = archive_info.WprArchiveInfo.FromFile(
        self.story_set_archive_info_file, cloud_storage.PUBLIC_BUCKET)
    self.assertEquals(new_recording,
                      read_archive_info.WprFilePathForStory(page1))
