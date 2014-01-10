# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Bitmap processing routines.

All functions accept a tuple of (pixels, width, channels) as the first argument.
Bounding box is a tuple (left, right, width, height).
"""

import imp
import os
import sys

from telemetry.core import build_extension, util


def _BuildModule(module_name):
  # Build the extension for telemetry users who don't use all.gyp.
  path = os.path.dirname(__file__)
  src_files = [os.path.join(path, 'bitmaptools.cc')]
  build_extension.BuildExtension(src_files, path, module_name)
  return imp.find_module(module_name, [path])


def _FindAndImport():
  found = util.FindSupportModule('bitmaptools')
  if not found:
    found = _BuildModule('bitmaptools')
  if not found:
    raise NotImplementedError('The bitmaptools module is not available.')
  return imp.load_module('bitmaptools', *found)


sys.modules['bitmaptools_ext'] = _FindAndImport()

# pylint: disable=W0401,F0401
from bitmaptools_ext import *
