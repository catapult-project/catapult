# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Bitmap processing routines.

All functions accept a tuple of (pixels, width, channels) as the first argument.
Bounding box is a tuple (left, right, width, height).
"""


def _FixDistutilsMsvcCompiler():
  # To avoid runtime mismatch, distutils should use the compiler which was used
  # to build python. But our module does not use the runtime much, so it should
  # be fine to build within a different environment.
  # See also: http://bugs.python.org/issue7511
  from distutils import msvc9compiler
  for version in [msvc9compiler.get_build_version(), 9.0, 10.0, 11.0, 12.0]:
    msvc9compiler.VERSION = version
    try:
      msvc9compiler.MSVCCompiler().initialize()
      break
    except Exception:
      pass


def _BuildExtension():
  """Builds the extension library on demand."""
  from distutils import log
  from distutils.core import Distribution, Extension
  import os
  import tempfile

  if os.name == 'nt':
    _FixDistutilsMsvcCompiler()

  build_dir = tempfile.mkdtemp()
  dirname = os.path.dirname(__file__)
  # Source file paths must be relative to current path.
  relpath = os.path.relpath(dirname, os.getcwd())
  src_files = [
    os.path.join(relpath, 'bitmaptools.cc')
  ]
  dist = Distribution({
    'ext_modules': [Extension('bitmaptools', src_files)]
  })
  dist.script_args = ['build_ext', '--build-temp', build_dir,
                      '--build-lib', dirname]
  dist.parse_command_line()
  log.set_threshold(log.DEBUG)
  dist.run_commands()
  dist.script_args = ['clean', '--build-temp', build_dir, '--all']
  dist.parse_command_line()
  log.set_threshold(log.DEBUG)
  dist.run_commands()


try:
  # Always re-build from source. No-op if source file older than the library.
  _BuildExtension()
except Exception:
  # TODO(tonyg): fetch from cloudstorage
  pass


try:
  # pylint: disable=W0401,F0401
  from .bitmaptools import *
except ImportError, e:
  raise NotImplementedError(
    'The bitmaptools module is not available for this platform.',
    e
  )
