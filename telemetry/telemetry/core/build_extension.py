# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


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
      return
    except Exception:
      pass
  raise Exception('Could not initialize MSVC compiler for distutils.')


def BuildExtension(sources, output_dir, extension_name):
  from distutils import log
  from distutils.core import Distribution, Extension
  import os
  import tempfile

  build_dir = tempfile.mkdtemp()
  # Source file paths must be relative to current path.
  cwd = os.getcwd()
  src_files = [os.path.relpath(filename, cwd) for filename in sources]

  ext = Extension(extension_name, src_files)

  if os.name == 'nt':
    _FixDistutilsMsvcCompiler()
    # VS 2010 does not generate manifest, see http://bugs.python.org/issue4431
    ext.extra_link_args = ['/MANIFEST']

  dist = Distribution({
    'ext_modules': [ext]
  })
  dist.script_args = ['build_ext', '--build-temp', build_dir,
                      '--build-lib', output_dir]
  dist.parse_command_line()
  log.set_threshold(log.DEBUG)
  dist.run_commands()
  dist.script_args = ['clean', '--build-temp', build_dir, '--all']
  dist.parse_command_line()
  log.set_threshold(log.DEBUG)
  dist.run_commands()


if __name__ == '__main__':
  import sys
  assert len(sys.argv) > 3, (
    'Usage: build.py source-files output-dir ext-name\n'
    'got: ' + str(sys.argv)
  )
  BuildExtension(sys.argv[1:-2], sys.argv[-2], sys.argv[-1])
