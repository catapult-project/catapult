// Copyright 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include <Python.h>
#include <string.h>


struct Box {
  Box() : left(), top(), right(), bottom() {}

  bool ParseArg(PyObject* obj) {
    int width;
    int height;
    if (!PyArg_ParseTuple(obj, "iiii", &left, &top, &width, &height))
      return false;
    if (left < 0 || top < 0 || width < 0 || height < 0) {
      PyErr_SetString(PyExc_ValueError, "Box dimensions must be non-negative.");
      return false;
    }
    right = left + width;
    bottom = top + height;
    return true;
  }

  PyObject* MakeObject() const {
    if (right <= left || bottom <= top)
      return Py_None;
    return Py_BuildValue("iiii", left, top, right - left, bottom - top);
  }

  void Union(int x, int y) {
    if (left > x) left = x;
    if (right <= x) right = x + 1;
    if (top > y) top = y;
    if (bottom <= y) bottom = y + 1;
  }

  int width() const { return right - left; }
  int height() const { return bottom - top; }

  int left;
  int top;
  int right;
  int bottom;
};


// Represents a bitmap buffer with a crop box.
struct Bitmap {
  Bitmap() {}

  ~Bitmap() {
    if (pixels.buf)
      PyBuffer_Release(&pixels);
  }

  bool ParseArg(PyObject* obj) {
    int width;
    int bpp;
    PyObject* box_object;
    if (!PyArg_ParseTuple(obj, "s*iiO", &pixels, &width, &bpp, &box_object))
      return false;
    if (width <= 0 || bpp <= 0) {
      PyErr_SetString(PyExc_ValueError, "Width and bpp must be positive.");
      return false;
    }

    row_stride = width * bpp;
    pixel_stride = bpp;
    total_size = pixels.len;
    row_size = row_stride;

    if (pixels.len % row_stride != 0) {
      PyErr_SetString(PyExc_ValueError, "Length must be a multiple of width "
                                        "and bpp.");
      return false;
    }

    if (!box.ParseArg(box_object))
      return false;

    if (box.bottom * row_stride > total_size ||
        box.right * pixel_stride > row_size) {
      PyErr_SetString(PyExc_ValueError, "Crop box overflows the bitmap.");
      return false;
    }

    total_size = (box.bottom - box.top) * row_stride;
    row_size = (box.right - box.left) * pixel_stride;
    data = reinterpret_cast<const unsigned char*>(pixels.buf) +
        box.top * row_stride + box.left * pixel_stride;
    return true;
  }

  Py_buffer pixels;
  Box box;
  // Points at the top-left pixel in |pixels.buf|.
  const unsigned char* data;
  // These counts are in bytes.
  int row_stride;
  int pixel_stride;
  int total_size;
  int row_size;
};


static
PyObject* Histogram(PyObject* self, PyObject* bmp_object) {
  Bitmap bmp;
  if (!bmp.ParseArg(bmp_object))
    return NULL;

  const int kLength = 3 * 256;
  int counts[kLength] = {};

  for (const unsigned char* row = bmp.data; row < bmp.data + bmp.total_size;
       row += bmp.row_stride) {
    for (const unsigned char* pixel = row; pixel < row + bmp.row_size;
       pixel += bmp.pixel_stride) {
      ++(counts[256 * 0 + pixel[0]]);
      ++(counts[256 * 1 + pixel[1]]);
      ++(counts[256 * 2 + pixel[2]]);
    }
  }

  PyObject* list = PyList_New(kLength);
  if (!list)
    return NULL;

  for (int i = 0; i < kLength; ++i)
    PyList_SetItem(list, i, PyInt_FromLong(counts[i]));

  return list;
}


static inline
bool PixelsEqual(const unsigned char* pixel1, const unsigned char* pixel2,
                 int tolerance) {
  // Note: this works for both RGB and RGBA. Alpha channel is ignored.
  return (abs(pixel1[0] - pixel2[0]) <= tolerance) &&
         (abs(pixel1[1] - pixel2[1]) <= tolerance) &&
         (abs(pixel1[2] - pixel2[2]) <= tolerance);
}

static inline
bool PixelsEqual(const unsigned char* pixel, int color, int tolerance) {
  unsigned char pixel2[3] = { color >> 16, color >> 8, color };
  return PixelsEqual(pixel, pixel2, tolerance);
}

static
PyObject* Equal(PyObject* self, PyObject* args) {
  PyObject* bmp_obj1;
  PyObject* bmp_obj2;
  int tolerance;
  if (!PyArg_ParseTuple(args, "OOi", &bmp_obj1, &bmp_obj2, &tolerance))
    return NULL;

  Bitmap bmp1, bmp2;
  if (!bmp1.ParseArg(bmp_obj1) || !bmp2.ParseArg(bmp_obj2))
    return NULL;

  if (bmp1.box.width() != bmp2.box.width() ||
      bmp1.box.height() != bmp2.box.height()) {
    PyErr_SetString(PyExc_ValueError, "Bitmap dimensions don't match.");
    return NULL;
  }

  bool simple_match = (tolerance == 0) &&
                      (bmp1.pixel_stride == 3) &&
                      (bmp2.pixel_stride == 3);
  for (const unsigned char *row1 = bmp1.data, *row2 = bmp2.data;
       row1 < bmp1.data + bmp1.total_size;
       row1 += bmp1.row_stride, row2 += bmp2.row_stride) {
    if (simple_match) {
      if (memcmp(row1, row2, bmp1.row_size) != 0)
        return Py_False;
      continue;
    }
    for (const unsigned char *pixel1 = row1, *pixel2 = row2;
         pixel1 < row1 + bmp1.row_size;
         pixel1 += bmp1.pixel_stride, pixel2 += bmp2.pixel_stride) {
      if (!PixelsEqual(pixel1, pixel2, tolerance))
        return Py_False;
    }
  }

  return Py_True;
}

static
PyObject* BoundingBox(PyObject* self, PyObject* args) {
  PyObject* bmp_object;
  int color;
  int tolerance;
  if (!PyArg_ParseTuple(args, "Oii", &bmp_object, &color, &tolerance))
    return NULL;

  Bitmap bmp;
  if (!bmp.ParseArg(bmp_object))
    return NULL;

  Box box;
  box.left = bmp.pixels.len;
  box.top = bmp.pixels.len;
  box.right = 0;
  box.bottom = 0;

  int count = 0;
  int y = 0;
  for (const unsigned char* row = bmp.data; row < bmp.data + bmp.total_size;
       row += bmp.row_stride, ++y) {
    int x = 0;
    for (const unsigned char* pixel = row; pixel < row + bmp.row_size;
         pixel += bmp.pixel_stride, ++x) {
      if (!PixelsEqual(pixel, color, tolerance))
        continue;
      box.Union(x, y);
      ++count;
    }
  }

  return Py_BuildValue("Oi", box.MakeObject(), count);
}

static
PyObject* Crop(PyObject* self, PyObject* bmp_object) {
  Bitmap bmp;
  if (!bmp.ParseArg(bmp_object))
    return NULL;

  int out_size = bmp.row_size * bmp.box.height();
  unsigned char* out = new unsigned char[out_size];
  unsigned char* dst = out;
  for (const unsigned char* row = bmp.data;
       row < bmp.data + bmp.total_size;
       row += bmp.row_stride, dst += bmp.row_size) {
    // No change in pixel_stride, so we can copy whole rows.
    memcpy(dst, row, bmp.row_size);
  }

  PyObject* result = Py_BuildValue("s#", out, out_size);
  delete[] out;
  return result;
}

static PyMethodDef module_methods[] = {
  {"Histogram", Histogram, METH_O,
    "Calculates histogram of bitmap colors. Returns a list of 3x256 ints."},
  {"Equal", Equal, METH_VARARGS,
    "Checks if the two bmps are equal."},
  {"BoundingBox", BoundingBox, METH_VARARGS,
    "Calculates bounding box of matching color."},
  {"Crop", Crop, METH_O,
    "Crops the bmp to crop box."},
  {NULL, NULL, 0, NULL}  /* sentinel */
};

PyMODINIT_FUNC initbitmaptools(void) {
  Py_InitModule("bitmaptools", module_methods);
}
