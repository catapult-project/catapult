#!/usr/bin/env python2.7
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import os
import subprocess
import sys
import unittest


def main():

  sys.path.append(os.path.dirname(__file__))
  suite = unittest.TestLoader().discover(
      os.path.dirname(__file__), pattern = '*_unittest.py')
  result = unittest.TextTestRunner(verbosity=2).run(suite)
  if result.wasSuccessful():
    sys.exit(0)
  else:
    sys.exit(1)


if __name__ == '__main__':
  main()
