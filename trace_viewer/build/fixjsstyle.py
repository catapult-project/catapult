# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

src_dir = os.path.join(os.path.dirname(__file__), '..')

sys.path.append(os.path.join(src_dir, 'third_party/python_gflags'))
sys.path.append(os.path.join(src_dir, 'third_party/closure_linter'))


from closure_linter import fixjsstyle
def main():
  os.chdir(src_dir)
  fixjsstyle.main()
