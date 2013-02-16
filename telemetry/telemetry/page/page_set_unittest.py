# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import tempfile
import unittest

from telemetry.page import page_set

simple_archive_info = """
{
"archives": {
  "data_01.wpr": ["http://www.foo.com/"],
  "data_02.wpr": ["http://www.bar.com/"]
}
}
"""

simple_set = """
{"description": "hello",
 "archive_data_file": "%s",
 "pages": [
   {"url": "http://www.foo.com/"},
   {"url": "http://www.bar.com/"}
 ]
}
"""

class TestPageSet(unittest.TestCase):
  def testSimpleSet(self):
    with tempfile.NamedTemporaryFile() as f:
      f.write(simple_archive_info)
      f.flush()
      archive_data_file = f.name

      with tempfile.NamedTemporaryFile() as f2:
        f2.write(simple_set % archive_data_file)
        f2.flush()
        ps = page_set.PageSet.FromFile(f2.name)

    self.assertEquals('hello', ps.description)
    self.assertEquals(archive_data_file, ps.archive_data_file)
    self.assertEquals(2, len(ps.pages))
    self.assertEquals('http://www.foo.com/', ps.pages[0].url)
    self.assertEquals('http://www.bar.com/', ps.pages[1].url)
    self.assertEquals('data_01.wpr', os.path.basename(ps.pages[0].archive_path))
    self.assertEquals('data_02.wpr', os.path.basename(ps.pages[1].archive_path))
