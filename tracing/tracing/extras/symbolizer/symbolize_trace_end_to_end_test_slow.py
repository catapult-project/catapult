#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tracing.extras.symbolizer import symbolize_trace

_THIS_DIR_PATH = os.path.abspath(os.path.dirname(__file__))
_TRACING_DIR = os.path.abspath(
    os.path.join(_THIS_DIR_PATH, '..', '..', '..'))
_PY_UTILS_PATH = os.path.abspath(os.path.join(
    _TRACING_DIR,
    '..',
    'common',
    'py_utils'))
sys.path.append(_PY_UTILS_PATH)
# pylint: disable=import-error
import py_utils.cloud_storage as cloud_storage


def _DownloadFromCloudStorage(path):
  print 'Downloading %s from gcs.' % (path)
  cloud_storage.GetIfChanged(path, cloud_storage.PARTNER_BUCKET)


def GetGzipCrc(path):
  args = 'gzip -v -l ' + path +  ' | awk \'{print $2}\' | tail -n 1'
  p = subprocess.Popen(args, shell=True, stdout=subprocess.PIPE)
  output, _ = p.communicate()
  return output


class SymbolizeTraceEndToEndTest(unittest.TestCase):
  def testMacv1(self):
    if sys.platform != 'darwin':
      return

    # The corresponding macOS Chrome symbols must be uploaded to
    # "gs://chrome-partner-telemetry/desktop-symbolizer-test/61.0.3135.4/mac64/"
    # "Google Chrome.dSYM.tar.bz2"
    # since the waterfall bots do not have access to the chrome-unsigned bucket.
    trace_presymbolization_path = os.path.join(
        _THIS_DIR_PATH, 'data', 'mac_trace_v1_presymbolization.json.gz')
    _DownloadFromCloudStorage(trace_presymbolization_path)

    trace_postsymbolization_path = os.path.join(
        _THIS_DIR_PATH, 'data', 'mac_trace_v1_postsymbolization.json.gz')
    _DownloadFromCloudStorage(trace_postsymbolization_path)

    _, temporary_trace = tempfile.mkstemp(suffix='.json.gz')
    try:
      shutil.copy(trace_presymbolization_path, temporary_trace)
      self.assertTrue(symbolize_trace.main(['--only-symbolize-chrome-symbols',
                                            '--no-backup',
                                            '--cloud-storage-bucket',
                                            cloud_storage.PARTNER_BUCKET,
                                            temporary_trace]))
      temporary_trace_crc = GetGzipCrc(temporary_trace)
      expected_crc = GetGzipCrc(trace_postsymbolization_path)
    finally:
      if os.path.exists(temporary_trace):
        os.remove(temporary_trace)
    self.assertEquals(temporary_trace_crc, expected_crc)


if __name__ == '__main__':
  unittest.main()
