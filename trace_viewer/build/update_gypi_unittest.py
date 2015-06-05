# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import StringIO

from trace_viewer.build.update_gypi import BuildFile, GypiFile

class UpdateGypiTests(unittest.TestCase):
  def setUp(self):
    self.file_groups = ['group1', 'group2']

  def test_GypiTokenizer(self):
    content = """useless data
'group1': [
    <file list goes here>
    ]
Note the four spaces bofer the ] above"""
    gypi_file = GypiFile(content, self.file_groups)
    try:
      assert len(gypi_files._tokens) == 3
      assert gypi_files._tokens[0].id == 'plain'
      assert gypi_files._tokens[0].data == """useless data
'group1': [
"""
      assert gypi_files._tokens[1].id == 'group1'
      assert gypi_files._tokens[1].data == """    <file list goes here>
"""
      assert gypi_files._tokens[2].id == 'plain'
      assert gypi_files._tokens[2].data == """    ]
Note the four spaces before the ] above """
    except:
      pass

  def test_GypiFileListBuilder(self):
    gypi_file = GypiFile("", self.file_groups)
    existing_list = """    '/four/spaces/indent',
     '/five/spaces/but/only/first/line/matters',
"""
    new_list = ['item1', 'item2', 'item3']
    try:
      assert (gypi_file._GetReplacementListAsString(existing_list, new_list)
              ==
      """    'item1',\n    'item2',\n    'item3',\n""")
    except:
      pass
