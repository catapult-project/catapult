# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import base64
import cStringIO

from telemetry.core import util

util.AddDirToPythonPath(util.GetTelemetryDir(), 'third_party', 'png')
import png  # pylint: disable=F0401


class RgbaColor(object):
  """Encapsulates an RGBA color retreived from a Bitmap"""

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
    assert self.IsEqual(RgbaColor(r, g, b), tolerance)

  def AssertIsRGBA(self, r, g, b, a, tolerance=0):
    assert self.IsEqual(RgbaColor(r, g, b, a), tolerance)


class Bitmap(object):
  """Utilities for parsing and inspecting a bitmap."""

  def __init__(self, bpp, width, height, pixels, metadata=None):
    assert bpp in [3, 4], 'Invalid bytes per pixel'
    assert width > 0, 'Invalid width'
    assert height > 0, 'Invalid height'
    assert pixels, 'Must specify pixels'
    assert bpp * width * height == len(pixels), 'Dimensions and pixels mismatch'

    self._bpp = bpp
    self._width = width
    self._height = height
    self._pixels = pixels
    self._metadata = metadata or {}

  @property
  def bpp(self):
    """Bytes per pixel."""
    return self._bpp

  @property
  def width(self):
    """Width of the bitmap."""
    return self._width

  @property
  def height(self):
    """Height of the bitmap."""
    return self._height

  @property
  def pixels(self):
    """Flat pixel array of the bitmap."""
    if type(self._pixels) is not bytearray:
      self._pixels = bytearray(self._pixels)
    return self._pixels

  @property
  def metadata(self):
    self._metadata['size'] = (self.width, self.height)
    self._metadata['alpha'] = self.bpp == 4
    self._metadata['bitdepth'] = 8
    return self._metadata

  def GetPixelColor(self, x, y):
    """Returns a RgbaColor for the pixel at (x, y)."""
    base = self._bpp * (y * self._width + x)
    if self._bpp == 4:
      return RgbaColor(self._pixels[base + 0], self._pixels[base + 1],
                       self._pixels[base + 2], self._pixels[base + 3])
    return RgbaColor(self._pixels[base + 0], self._pixels[base + 1],
                     self._pixels[base + 2])

  def WritePngFile(self, path):
    with open(path, "wb") as f:
      png.Writer(**self.metadata).write_array(f, self.pixels)

  @staticmethod
  def FromPng(png_data):
    width, height, pixels, meta = png.Reader(bytes=png_data).read_flat()
    return Bitmap(4 if meta['alpha'] else 3, width, height, pixels, meta)

  @staticmethod
  def FromPngFile(path):
    with open(path, "rb") as f:
      return Bitmap.FromPng(f.read())

  @staticmethod
  def FromBase64Png(base64_png):
    return Bitmap.FromPng(base64.b64decode(base64_png))

  def IsEqual(self, other, tolerance=0):
    """Determines whether two Bitmaps are identical within a given tolerance."""

    # Dimensions must be equal
    if self.width != other.width or self.height != other.height:
      return False

    # Loop over each pixel and test for equality
    if tolerance or self.bpp != other.bpp:
      for y in range(self.height):
        for x in range(self.width):
          c0 = self.GetPixelColor(x, y)
          c1 = other.GetPixelColor(x, y)
          if not c0.IsEqual(c1, tolerance):
            return False
    else:
      return self.pixels == other.pixels

    return True

  def Diff(self, other):
    """Returns a new Bitmap that represents the difference between this image
    and another Bitmap."""

    # Output dimensions will be the maximum of the two input dimensions
    out_width = max(self.width, other.width)
    out_height = max(self.height, other.height)

    diff = [[0 for x in xrange(out_width * 3)] for x in xrange(out_height)]

    # Loop over each pixel and write out the difference
    for y in range(out_height):
      for x in range(out_width):
        if x < self.width and y < self.height:
          c0 = self.GetPixelColor(x, y)
        else:
          c0 = RgbaColor(0, 0, 0, 0)

        if x < other.width and y < other.height:
          c1 = other.GetPixelColor(x, y)
        else:
          c1 = RgbaColor(0, 0, 0, 0)

        offset = x * 3
        diff[y][offset] = abs(c0.r - c1.r)
        diff[y][offset+1] = abs(c0.g - c1.g)
        diff[y][offset+2] = abs(c0.b - c1.b)

    # This particular method can only save to a file, so the result will be
    # written into an in-memory buffer and read back into a Bitmap
    diff_img = png.from_array(diff, mode='RGB')
    output = cStringIO.StringIO()
    try:
      diff_img.save(output)
      diff = Bitmap.FromPng(output.getvalue())
    finally:
      output.close()

    return diff

  def GetBoundingBox(self, color, tolerance=0):
    """Returns a (top, left, width, height) tuple of the minimum box
       surrounding all occurences of |color|."""
    # TODO(szym): Implement this.
    raise NotImplementedError("GetBoundingBox not yet implemented.")

  def Crop(self, top, left, width, height):
    """Crops the current bitmap down to the specified box.

    TODO(szym): Make this O(1).
    """
    if (left < 0 or top < 0 or
        (left + width) > self.width or
        (top + height) > self.height):
      raise ValueError('Invalid dimensions')

    img_data = [[0 for x in xrange(width * self.bpp)]
                for y in xrange(height)]

    # Copy each pixel in the sub-rect.
    # TODO(tonyg): Make this faster by avoiding the copy and artificially
    # restricting the dimensions.
    for y in range(height):
      for x in range(width):
        c = self.GetPixelColor(x + left, y + top)
        offset = x * self.bpp
        img_data[y][offset] = c.r
        img_data[y][offset + 1] = c.g
        img_data[y][offset + 2] = c.b
        if self.bpp == 4:
          img_data[y][offset + 3] = c.a

    # This particular method can only save to a file, so the result will be
    # written into an in-memory buffer and read back into a Bitmap
    crop_img = png.from_array(img_data, mode='RGBA' if self.bpp == 4 else 'RGB')
    output = cStringIO.StringIO()
    try:
      crop_img.save(output)
      width, height, pixels, meta = png.Reader(
          bytes=output.getvalue()).read_flat()
      self._width = width
      self._height = height
      self._pixels = pixels
      self._metadata = meta
    finally:
      output.close()

    return self

  def ColorHistogram(self):
    """Returns a histogram of the pixel colors in this Bitmap."""
    # TODO(szym): Implement this.
    raise NotImplementedError("ColorHistogram not yet implemented.")
