#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# pylint: disable=line-too-long
# To upload test files, use the command:
# <path_to_depot_tools>/upload_to_google_storage.py --bucket chrome-partner-telemetry <path_to_data_dir>/linux_trace_v2_breakpad_postsymbolization.json.gz
#
# To run this test suite, use ./tracing/bin/run_symbolizer_tests

import binascii
import gzip
import json
import os
import shutil
import sys
import tempfile
import unittest

from tracing.extras.symbolizer import symbolize_trace

_THIS_DIR_PATH = os.path.abspath(os.path.dirname(__file__))
_TRACING_DIR = os.path.abspath(
    os.path.join(_THIS_DIR_PATH,
                 os.path.pardir,
                 os.path.pardir,
                 os.path.pardir))
_PY_UTILS_PATH = os.path.abspath(os.path.join(
    _TRACING_DIR,
    os.path.pardir,
    'common',
    'py_utils'))
sys.path.append(_PY_UTILS_PATH)
# pylint: disable=import-error
import py_utils.cloud_storage as cloud_storage


def _DownloadFromCloudStorage(path):
  print 'Downloading %s from gcs.' % (path)
  cloud_storage.GetIfChanged(path, cloud_storage.PARTNER_BUCKET)


def GetJSonCrc(root):
  checksum = 0
  if isinstance(root, dict):
    for key, value in root.iteritems():
      checksum = checksum ^ (GetJSonCrc(key) + GetJSonCrc(value))
  elif isinstance(root, list):
    for value in root:
      checksum = checksum ^ GetJSonCrc(value)
  else:
    checksum = binascii.crc32(json.dumps(root))
  return checksum


def GetTraceCrc(filename):
  with gzip.open(filename, 'rb') as fd:
    content = json.loads(fd.read())
    checksum = GetJSonCrc(content)
  return checksum


class SymbolizeTraceEndToEndTest(unittest.TestCase):

  def _RunSymbolizationOnTrace(self, pre_symbolization, post_symbolization,
                               extra_options):
    trace_presymbolization_path = os.path.join(
        _THIS_DIR_PATH, 'data', pre_symbolization)
    _DownloadFromCloudStorage(trace_presymbolization_path)
    self.assertTrue(os.path.exists(trace_presymbolization_path))

    trace_postsymbolization_path = os.path.join(
        _THIS_DIR_PATH, 'data', post_symbolization)
    _DownloadFromCloudStorage(trace_postsymbolization_path)
    self.assertTrue(os.path.exists(trace_postsymbolization_path))

    temporary_fd, temporary_trace = tempfile.mkstemp(suffix='.json.gz')

    symbolization_options = ['--only-symbolize-chrome-symbols',
                             '--no-backup',
                             '--cloud-storage-bucket',
                             cloud_storage.PARTNER_BUCKET,
                             temporary_trace]

    symbolization_options.extend(extra_options)

    # On windows, a pre-built version of addr2line-pdb is provided.
    if sys.platform == 'win32':
      addr2line_path = os.path.join(
          _THIS_DIR_PATH, 'data', 'addr2line-pdb.exe')
      _DownloadFromCloudStorage(addr2line_path)
      self.assertTrue(os.path.exists(addr2line_path))
      symbolization_options += ['--addr2line-executable', addr2line_path]

    # Execute symbolization and compare results with the expected trace.
    temporary_trace_crc = None
    expected_crc = None
    try:
      shutil.copy(trace_presymbolization_path, temporary_trace)
      self.assertTrue(symbolize_trace.main(symbolization_options))
      temporary_trace_crc = GetTraceCrc(temporary_trace)
      expected_crc = GetTraceCrc(trace_postsymbolization_path)
    finally:
      os.close(temporary_fd)
      if os.path.exists(temporary_trace):
        os.remove(temporary_trace)

    # Checksums must match.
    self.assertTrue(temporary_trace_crc and expected_crc and
                    temporary_trace_crc == expected_crc)

  def testMacv1(self):
    if sys.platform != 'darwin':
      return

    # The corresponding macOS Chrome symbols must be uploaded to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3135.4/mac64/"
    # "Google Chrome.dSYM.tar.bz2"
    # since the waterfall bots do not have access to the chrome-unsigned bucket.
    self._RunSymbolizationOnTrace('mac_trace_v1_presymbolization.json.gz',
                                  'mac_trace_v1_postsymbolization.json.gz',
                                  [])

  def testMacv1Breakpad(self):
    # The trace produced by the breakpad symbolizer is slightly different for
    # function name that are omitted. Breakpad is producing "<name omitted>"
    # for some function name. See:
    # https://cs.chromium.org/chromium/src/breakpad/src/common/dwarf_cu_to_module.cc?l=551&rcl=7a65a47345a86c9e9a3fbc2e92a756a429a0c82f
    self._RunSymbolizationOnTrace(
        'mac_trace_v1_presymbolization.json.gz',
        'mac_trace_v1_breakpad_postsymbolisation.json.gz',
        ['--use-breakpad-symbols'])

  def testWin64v1(self):
    if sys.platform != 'win32':
      return

    # The corresponding Win64 Chrome symbols must be uploaded to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3130.0/"
    # "win64-pgo/chrome-win32-syms.zip"
    # and the corresponding executables to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3130.0/"
    # "win64-pgo/chrome-win64-pgo.zip"
    # since the waterfall bots do not have access to the chrome-unsigned bucket.
    self._RunSymbolizationOnTrace('windows_trace_v1_presymbolization.json.gz',
                                  'windows_trace_v1_postsymbolization.json.gz',
                                  [])

  def testWin64v2(self):
    if sys.platform != 'win32':
      return

    # The corresponding Win64 Chrome symbols must be uploaded to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3142.0/"
    # "win64-pgo/chrome-win32-syms.zip"
    # and the corresponding executables to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3142.0/"
    # "win64-pgo/chrome-win64-pgo.zip"
    # since the waterfall bots do not have access to the chrome-unsigned bucket.
    self._RunSymbolizationOnTrace('windows_trace_v2_presymbolization.json.gz',
                                  'windows_trace_v2_postsymbolization.json.gz',
                                  [])


  def testLinuxv2(self):
    # The corresponding Linux breakpad symbols must be uploaded to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/64.0.3282.24/linux64/breakpad-info.zip"
    # since the waterfall bots do not have access to the chrome-unsigned bucket.
    self._RunSymbolizationOnTrace(
        'linux_trace_v2_presymbolization.json.gz',
        'linux_trace_v2_breakpad_postsymbolization.json.gz',
        ['--use-breakpad-symbols'])


if __name__ == '__main__':
  unittest.main()
