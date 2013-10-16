# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import cStringIO

from telemetry.core import util

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'png')
import png  # pylint: disable=F0401


class PngColor(object):
  """Encapsulates an RGB color retreived from a PngBitmap"""

  def __init__(self, r, g, b, a=255):
    self.r = r
    self.g = g
    self.b = b
    self.a = a

  def IsEqual(self, expected_color, tolerance=0):
    """Verifies that the color is within a given tolerance of
    the expected color"""
    r_diff = abs(self.r - expected_color.r)
    g_diff = abs(self.g - expected_color.g)
    b_diff = abs(self.b - expected_color.b)
    a_diff = abs(self.a - expected_color.a)
    return (r_diff <= tolerance and g_diff <= tolerance
        and b_diff <= tolerance and a_diff <= tolerance)

  def AssertIsRGB(self, r, g, b, tolerance=0):
    assert self.IsEqual(PngColor(r, g, b), tolerance)

  def AssertIsRGBA(self, r, g, b, a, tolerance=0):
    assert self.IsEqual(PngColor(r, g, b, a), tolerance)


class PngBitmap(object):
  """Utilities for parsing and inspecting a PNG"""

  def __init__(self, png_data):
    self._png_data = png_data
    self._png = png.Reader(bytes=self._png_data)
    rgba8_data = self._png.asRGBA8()
    self._width = rgba8_data[0]
    self._height = rgba8_data[1]
    self._pixels = list(rgba8_data[2])
    self._metadata = rgba8_data[3]

  @property
  def width(self):
    """Width of the snapshot"""
    return self._width

  @property
  def height(self):
    """Height of the snapshot"""
    return self._height

  def GetPixelColor(self, x, y):
    """Returns a PngColor for the pixel at (x, y)"""
    row = self._pixels[y]
    offset = x * 4
    return PngColor(row[offset], row[offset+1], row[offset+2], row[offset+3])

  def WriteFile(self, path):
    with open(path, "wb") as f:
      f.write(self._png_data)

  @staticmethod
  def FromFile(path):
    with open(path, "rb") as f:
      return PngBitmap(f.read())

  @staticmethod
  def FromBase64(base64_png):
    return PngBitmap(base64.b64decode(base64_png))

  def IsEqual(self, expected_png, tolerance=0):
    """Verifies that two PngBitmaps are identical within a given tolerance"""

    # Dimensions must be equal
    if self.width != expected_png.width or self.height != expected_png.height:
      return False

    # Loop over each pixel and test for equality
    for y in range(self.height):
      for x in range(self.width):
        c0 = self.GetPixelColor(x, y)
        c1 = expected_png.GetPixelColor(x, y)
        if not c0.IsEqual(c1, tolerance):
          return False

    return True

  def Diff(self, other_png):
    """Returns a new PngBitmap that represents the difference between this image
    and another PngBitmap"""

    # Output dimensions will be the maximum of the two input dimensions
    out_width = max(self.width, other_png.width)
    out_height = max(self.height, other_png.height)

    diff = [[0 for x in xrange(out_width * 3)] for x in xrange(out_height)]

    # Loop over each pixel and write out the difference
    for y in range(out_height):
      for x in range(out_width):
        if x < self.width and y < self.height:
          c0 = self.GetPixelColor(x, y)
        else:
          c0 = PngColor(0, 0, 0, 0)

        if x < other_png.width and y < other_png.height:
          c1 = other_png.GetPixelColor(x, y)
        else:
          c1 = PngColor(0, 0, 0, 0)

        offset = x * 3
        diff[y][offset] = abs(c0.r - c1.r)
        diff[y][offset+1] = abs(c0.g - c1.g)
        diff[y][offset+2] = abs(c0.b - c1.b)

    # This particular method can only save to a file, so the result will be
    # written into an in-memory buffer and read back into a PngBitmap
    diff_img = png.from_array(diff, mode='RGB')
    output = cStringIO.StringIO()
    try:
      diff_img.save(output)
      diff_png = PngBitmap(output.getvalue())
    finally:
      output.close()

    return diff_png

  def Crop(self, left, top, width, height):
    """Returns a new PngBitmap that represents the specified sub-rect of this
    PngBitmap"""

    if (left < 0 or top < 0 or
        (left + width) > self.width or
        (top + height) > self.height):
      raise Exception('Invalid dimensions')

    img_data = [[0 for x in xrange(width * 4)] for x in xrange(height)]

    # Copy each pixel in the sub-rect
    for y in range(height):
      for x in range(width):
        c = self.GetPixelColor(x + left, y + top)
        offset = x * 4
        img_data[y][offset] = c.r
        img_data[y][offset+1] = c.g
        img_data[y][offset+2] = c.b
        img_data[y][offset+3] = c.a

    # This particular method can only save to a file, so the result will be
    # written into an in-memory buffer and read back into a PngBitmap
    crop_img = png.from_array(img_data, mode='RGBA')
    output = cStringIO.StringIO()
    try:
      crop_img.save(output)
      crop_png = PngBitmap(output.getvalue())
    finally:
      output.close()

    return crop_png
