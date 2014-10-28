# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest
import shutil
import tempfile

from telemetry.util import file_handle


class FileHandleUnittest(unittest.TestCase):

  def setUp(self):
    self.temp_file_txt = tempfile.NamedTemporaryFile(
        suffix='.txt', delete=False)
    self.abs_path_html = tempfile.NamedTemporaryFile(
        suffix='.html', delete=False).name

  def tearDown(self):
    os.remove(self.abs_path_html)

  def testCreatingFileHandle(self):
    fh1 = file_handle.FromTempFile(self.temp_file_txt)
    self.assertEquals(fh1.extension, '.txt')

    fh2 = file_handle.FromFilePath(self.abs_path_html)
    self.assertEquals(fh2.extension, '.html')
    self.assertNotEquals(fh1.id, fh2.id)

  def testOutputFiles(self):
    fh1 = file_handle.FromTempFile(self.temp_file_txt)
    fh2 = file_handle.FromFilePath(self.abs_path_html)
    tmpdir = tempfile.mkdtemp()
    try:
      file_ids_to_paths = file_handle.OutputFiles([fh1, fh2], tmpdir)
      expected_output_file_1_path = os.path.join(tmpdir, str(fh1.id) + '.txt')
      expected_output_file_2_path = os.path.join(tmpdir, str(fh2.id) + '.html')
      self.assertEqual(file_ids_to_paths[fh1.id], expected_output_file_1_path)
      self.assertEqual(file_ids_to_paths[fh2.id], expected_output_file_2_path)

      # Test that the files are actually output.
      self.assertTrue(os.path.exists(expected_output_file_1_path))
      self.assertTrue(os.path.exists(expected_output_file_2_path))
    finally:
      shutil.rmtree(tmpdir)
