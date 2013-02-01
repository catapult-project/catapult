# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import shutil
import tempfile
import unittest

from telemetry import page_set_archive_info

class MockPage(object):
  def __init__(self, url):
    self.url = url

url1 = 'http://www.foo.com/'
url2 = 'http://www.bar.com/'
url3 = 'http://www.baz.com/'
recording1 = 'data_001.wpr'
recording2 = 'data_002.wpr'
archive_info_contents = ("""
{
"archives": {
  "%s": ["%s", "%s"],
  "%s": ["%s"]
}
}
""" % (recording1, url1, url2, recording2, url3))
page1 = MockPage(url1)
page2 = MockPage(url2)
page3 = MockPage(url3)

class TestPageSetArchiveInfo(unittest.TestCase):
  def setUp(self):
    self.tmp_dir = tempfile.mkdtemp()
    # Write the metadata.
    self.page_set_archive_info_file = os.path.join(self.tmp_dir, 'info.json')
    f = open(self.page_set_archive_info_file, 'w')
    f.write(archive_info_contents)
    f.close()

    # Write the existing .wpr files.
    for i in [1, 2]:
      f = open(os.path.join(self.tmp_dir, ('data_00%d.wpr' % i)), 'w')
      f.write(archive_info_contents)
      f.close()

    # Create the PageSetArchiveInfo object to be tested.
    self.archive_info = page_set_archive_info.PageSetArchiveInfo.FromFile(
        self.page_set_archive_info_file, '/tmp/pageset.json')

  def tearDown(self):
    shutil.rmtree(self.tmp_dir)

  def testReadingArchiveInfo(self):
    self.assertEquals(recording1, os.path.basename(
        self.archive_info.WprFilePathForPage(page1)))
    self.assertEquals(recording1, os.path.basename(
        self.archive_info.WprFilePathForPage(page2)))
    self.assertEquals(recording2, os.path.basename(
        self.archive_info.WprFilePathForPage(page3)))

  def testModifications(self):
    new_recording1 = 'data_003.wpr'
    new_temp_recording = os.path.join(self.tmp_dir, 'recording.wpr')
    f = open(new_temp_recording, 'w')
    f.write('wpr data')
    f.close()

    self.archive_info.AddNewTemporaryRecording(new_temp_recording)

    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForPage(page1))
    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForPage(page2))
    self.assertEquals(new_temp_recording,
                      self.archive_info.WprFilePathForPage(page3))

    self.archive_info.AddRecordedPages([page2])

    self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, new_recording1)))
    self.assertFalse(os.path.exists(
        os.path.join(self.tmp_dir, new_temp_recording)))

    self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, recording1)))
    self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, recording2)))

    new_recording2 = 'data_004.wpr'
    f = open(new_temp_recording, 'w')
    f.write('wpr data')
    f.close()

    self.archive_info.AddNewTemporaryRecording(new_temp_recording)
    self.archive_info.AddRecordedPages([page3])

    self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, new_recording2)))
    self.assertFalse(os.path.exists(
        os.path.join(self.tmp_dir, new_temp_recording)))

    self.assertTrue(os.path.exists(os.path.join(self.tmp_dir, recording1)))
    # recording2 is no longer needed, so it was deleted.
    self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, recording2)))
