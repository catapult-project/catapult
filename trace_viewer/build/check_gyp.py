# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from trace_viewer.build import check_common

GYP_FILE = "trace_viewer.gyp"

def GypCheck():
  f = open(GYP_FILE, 'r')
  gyp = f.read()
  f.close()

  data = eval(gyp)
  listed_files = []
  for group in check_common.FILE_GROUPS:
    listed_files.extend(map(os.path.normpath, data["variables"][group]))

  return check_common.CheckCommon(GYP_FILE, listed_files)

if __name__ == '__main__':
  print GypCheck()
