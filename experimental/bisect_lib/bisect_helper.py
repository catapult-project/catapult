#!/usr/bin/python2.7

# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))

from bisect_lib import chromium_revisions


def main(argv):
  if argv[1] == 'query_revision_info':
    print json.dumps(chromium_revisions.revision_info(argv[2]))
  elif argv[1] == 'revision_range':
    print json.dumps(chromium_revisions.revision_range(argv[2], argv[3]))
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
