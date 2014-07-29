# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest
import StringIO

from trace_viewer.build.update_gyp_and_gn import BuildFile, GnFile, GypFile

class UpdateGypAndGnTests(unittest.TestCase):
  def setUp(self):
    self.file_groups = ['group1', 'group2']

  def test_GnTokenizer(self):
    content = """useless data
group1 = [
"/a/file",
 <there can be useless things here too>
"/another/file",
]
More useless things"""
    gn_file = GnFile(content, self.file_groups)
    try:
      assert len(gn_files._tokens) == 3
      assert gn_files._tokens[0].id == 'plain'
      assert gn_files._tokens[0].data == """useless data
group1 = [
"""
      assert gn_files._tokens[1].id == 'group1'
      assert gn_files._tokens[1].data == """"/a/file",
 <there can be useless things here too>
"/another/file",
"""
      assert gn_files._tokens[2].id == 'plain'
      assert gn_files._tokens[2].data == """]
More useless things"""
    except:
      pass

  def test_GypTokenizer(self):
    content = """useless data
'group1': [
    <file list goes here>
    ]
Note the four spaces bofer the ] above"""
    gyp_file = GypFile(content, self.file_groups)
    try:
      assert len(gyp_files._tokens) == 3
      assert gyp_files._tokens[0].id == 'plain'
      assert gyp_files._tokens[0].data == """useless data
'group1': [
"""
      assert gyp_files._tokens[1].id == 'group1'
      assert gyp_files._tokens[1].data == """    <file list goes here>
"""
      assert gyp_files._tokens[2].id == 'plain'
      assert gyp_files._tokens[2].data == """    ]
Note the four spaces before the ] above """
    except:
      pass

  def test_GnFileListBuilder(self):
    gn_file = GnFile("", self.file_groups)
    existing_list_as_string = """    "/four/spaces/indent",
    "/four/spaces/again",
"""
    new_list = ['item1', 'item2', 'item3']
    try:
      assert (gn_file._GetReplacementListAsString(existing_list_as_string,
                                                 new_list)
              ==
      """    "item1",\n    "item2",\n    "item3",\n""")
    except:
      pass

  def test_GypFileListBuilder(self):
    gyp_file = GypFile("", self.file_groups)
    existing_list_as_string = """    '/four/spaces/indent',
     '/five/spaces/but/only/first/line/matters',
"""
    new_list = ['item1', 'item2', 'item3']
    try:
      assert (gyp_file._GetReplacementListAsString(existing_list_as_string,
                                                 new_list)
              ==
      """    'item1',\n    'item2',\n    'item3',\n""")
    except:
      pass
