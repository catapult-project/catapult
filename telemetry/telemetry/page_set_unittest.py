# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import tempfile
import unittest

from telemetry import page_set

simple_set = """
{"description": "hello",
 "archive_path": "foo.wpr",
 "pages": [
   {"url": "http://www.foo.com/"}
 ]
}
"""

class TestPageSet(unittest.TestCase):
  def testSimpleSet(self):
    with tempfile.NamedTemporaryFile() as f:
      f.write(simple_set)
      f.flush()
      ps = page_set.PageSet.FromFile(f.name)

    self.assertEquals('hello', ps.description)
    self.assertEquals('foo.wpr', ps.archive_path)
    self.assertEquals(1, len(ps.pages))
    self.assertEquals('http://www.foo.com/', ps.pages[0].url)
