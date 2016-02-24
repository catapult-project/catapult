# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import tempfile
import unittest

from profile_chrome import trace_packager


class TracePackagerTest(unittest.TestCase):
  def testJsonTraceMerging(self):
    t1 = {'traceEvents': [{'ts': 123, 'ph': 'b'}]}
    t2 = {'traceEvents': [], 'stackFrames': ['blah']}

    # Both trace files will be merged to a third file and will get deleted in
    # the process, so there's no need for NamedTemporaryFile to do the
    # deletion.
    with tempfile.NamedTemporaryFile(delete=False) as f1, \
        tempfile.NamedTemporaryFile(delete=False) as f2:
      f1.write(json.dumps(t1))
      f2.write(json.dumps(t2))
      f1.flush()
      f2.flush()

      with tempfile.NamedTemporaryFile() as output:
        trace_packager.PackageTraces([f1.name, f2.name],
                                     output.name,
                                     compress=False,
                                     write_json=True)
        with open(output.name) as output:
          output = json.load(output)
          self.assertEquals(output['traceEvents'], t1['traceEvents'])
          self.assertEquals(output['stackFrames'], t2['stackFrames'])
