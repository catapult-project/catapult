# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import os

from telemetry.core import util
from telemetry.core.backends import png_bitmap


# This is a simple base64 encoded 2x2 PNG which contains, in order, a single
# Red, Yellow, Blue, and Green pixel.
test_png = """
iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91
JpzAAAAAXNSR0IArs4c6QAAAAlwSFlzAAALEwAACx
MBAJqcGAAAABZJREFUCNdj/M/AwPCfgYGB4T/DfwY
AHAAD/iOWZXsAAAAASUVORK5CYII=
"""


test_png_path = os.path.join(util.GetUnittestDataDir(), 'test_png.png')
test_png_2_path = os.path.join(util.GetUnittestDataDir(), 'test_png_2.png')


class PngBitmapTest(unittest.TestCase):
  def testReadFromBase64(self):
    png = png_bitmap.PngBitmap.FromBase64(test_png)

    self.assertEquals(2, png.width)
    self.assertEquals(2, png.height)

    png.GetPixelColor(0, 0).AssertIsRGB(255, 0, 0)
    png.GetPixelColor(1, 1).AssertIsRGB(0, 255, 0)
    png.GetPixelColor(0, 1).AssertIsRGB(0, 0, 255)
    png.GetPixelColor(1, 0).AssertIsRGB(255, 255, 0)

  def testReadFromFile(self):
    file_png = png_bitmap.PngBitmap.FromFile(test_png_path)

    self.assertEquals(2, file_png.width)
    self.assertEquals(2, file_png.height)

    file_png.GetPixelColor(0, 0).AssertIsRGB(255, 0, 0)
    file_png.GetPixelColor(1, 1).AssertIsRGB(0, 255, 0)
    file_png.GetPixelColor(0, 1).AssertIsRGB(0, 0, 255)
    file_png.GetPixelColor(1, 0).AssertIsRGB(255, 255, 0)

  def testIsEqual(self):
    png = png_bitmap.PngBitmap.FromBase64(test_png)
    file_png = png_bitmap.PngBitmap.FromFile(test_png_path)
    self.assertTrue(png.IsEqual(file_png))

  def testDiff(self):
    file_png = png_bitmap.PngBitmap.FromFile(test_png_path)
    file_png_2 = png_bitmap.PngBitmap.FromFile(test_png_2_path)

    diff_png = file_png.Diff(file_png)

    self.assertEquals(2, diff_png.width)
    self.assertEquals(2, diff_png.height)

    diff_png.GetPixelColor(0, 0).AssertIsRGB(0, 0, 0)
    diff_png.GetPixelColor(1, 1).AssertIsRGB(0, 0, 0)
    diff_png.GetPixelColor(0, 1).AssertIsRGB(0, 0, 0)
    diff_png.GetPixelColor(1, 0).AssertIsRGB(0, 0, 0)

    diff_png = file_png.Diff(file_png_2)

    self.assertEquals(3, diff_png.width)
    self.assertEquals(3, diff_png.height)

    diff_png.GetPixelColor(0, 0).AssertIsRGB(0, 255, 255)
    diff_png.GetPixelColor(1, 1).AssertIsRGB(255, 0, 255)
    diff_png.GetPixelColor(0, 1).AssertIsRGB(255, 255, 0)
    diff_png.GetPixelColor(1, 0).AssertIsRGB(0, 0, 255)

    diff_png.GetPixelColor(0, 2).AssertIsRGB(255, 255, 255)
    diff_png.GetPixelColor(1, 2).AssertIsRGB(255, 255, 255)
    diff_png.GetPixelColor(2, 0).AssertIsRGB(255, 255, 255)
    diff_png.GetPixelColor(2, 1).AssertIsRGB(255, 255, 255)
    diff_png.GetPixelColor(2, 2).AssertIsRGB(255, 255, 255)
