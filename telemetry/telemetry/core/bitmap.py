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
    self._crop_box = None

  @property
  def bpp(self):
    """Bytes per pixel."""
    return self._bpp

  @property
  def width(self):
    """Width of the bitmap."""
    if self._crop_box:
      return self._crop_box[2]
    return self._width

  @property
  def height(self):
    """Height of the bitmap."""
    if self._crop_box:
      return self._crop_box[3]
    return self._height

  @property
  def _as_tuple(self):
    # If we got a list of ints, we need to convert it into a byte buffer.
    pixels = self._pixels
    if type(pixels) is not bytearray:
      pixels = bytearray(pixels)
    if type(pixels) is not bytes:
      pixels = bytes(pixels)
    crop_box = self._crop_box or (0, 0, self._width, self._height)
    return pixels, self._width, self._bpp, crop_box

  @property
  def pixels(self):
    """Flat pixel array of the bitmap."""
    if self._crop_box:
      from telemetry.core import bitmaptools
      self._pixels = bitmaptools.Crop(self._as_tuple)
      _, _, self._width, self._height = self._crop_box
      self._crop_box = None
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
    pixels = self.pixels
    base = self._bpp * (y * self._width + x)
    if self._bpp == 4:
      return RgbaColor(pixels[base + 0], pixels[base + 1],
                       pixels[base + 2], pixels[base + 3])
    return RgbaColor(pixels[base + 0], pixels[base + 1],
                     pixels[base + 2])

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
    """Determines whether two Bitmaps are identical within a given tolerance.
    Ignores alpha channel."""
    from telemetry.core import bitmaptools
    # pylint: disable=W0212
    return bitmaptools.Equal(self._as_tuple, other._as_tuple, tolerance)

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
    """Finds the minimum box surrounding all occurences of |color|.
    Returns: (top, left, width, height), match_count
    Ignores the alpha channel."""
    from telemetry.core import bitmaptools
    int_color = (color.r << 16) | (color.g << 8) | color.b
    return bitmaptools.BoundingBox(self._as_tuple, int_color, tolerance)

  def Crop(self, left, top, width, height):
    """Crops the current bitmap down to the specified box."""
    cur_box = self._crop_box or (0, 0, self._width, self._height)
    cur_left, cur_top, cur_width, cur_height = cur_box

    if (left < 0 or top < 0 or
        (left + width) > cur_width or
        (top + height) > cur_height):
      raise ValueError('Invalid dimensions')

    self._crop_box = cur_left + left, cur_top + top, width, height
    return self

  def ColorHistogram(self):
    """Computes a histogram of the pixel colors in this Bitmap.
    Returns a list of 3x256 integers."""
    from telemetry.core import bitmaptools
    return bitmaptools.Histogram(self._as_tuple)
