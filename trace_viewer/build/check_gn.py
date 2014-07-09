# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from trace_viewer.build import check_common


GN_FILE = "BUILD.gn"


def ItemToFilename(item):
  assert item[0] == '"', "GN files use double-quotes, gyp uses single quotes"
  assert item[-1] == '"', "GN files use double-quotes, gyp uses single quotes"
  return item[1:-1]


def GnCheck():
  f = open(GN_FILE, 'r')
  gn = f.read()
  f.close()

  listed_files = []
  error = ""
  for group in check_common.FILE_GROUPS:
    expr = '%s = \[(.+?)\]\n' % group
    m = re.search(expr, gn, re.DOTALL)
    if not m:
      raise Exception('%s is malformed' % GN_FILE)
    g = m.group(1).strip()
    items = g.split(',')
    filenames = [ItemToFilename(item.strip()) for item in items
                 if len(item) > 0]

    error += check_common.CheckListedFilesSorted(GN_FILE, group, filenames)
    listed_files.extend(map(os.path.normpath, filenames))

  return error + check_common.CheckCommon(GN_FILE, listed_files)

if __name__ == '__main__':
  print GnCheck()
