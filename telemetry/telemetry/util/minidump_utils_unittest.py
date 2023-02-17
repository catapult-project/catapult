# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import six

if six.PY3:
  from unittest import mock

# pylint: disable=wrong-import-position
from telemetry.util import minidump_utils
# pylint: enable=wrong-import-position


@unittest.skipIf(six.PY2, 'Tested code is Python 3-only')
class GetCrashpadAnnotationUnittest(unittest.TestCase):
  """Test cases for GetCrashpadAnnotation() and its specific versions."""
  def setUp(self):
    self._dump_patcher = mock.patch.object(minidump_utils, 'DumpMinidump')
    self._dump_mock = self._dump_patcher.start()
    self.addCleanup(self._dump_patcher.stop)
    # pylint: disable=line-too-long
    self._dump_mock.return_value = """\
MDRawCrashpadInfo
  version = 1
  report_id = 95ebd8b0-1f08-4a39-9359-d26725ea9144
  client_id = 3826aae7-e60a-4ef5-89af-e9d00ef7fd06
  simple_annotations["lsb-release"] = Debian GNU/Linux rodete
  simple_annotations["plat"] = Linux
  simple_annotations["prod"] = Chrome_Linux
  simple_annotations["ver"] = 112.0.5599.0
  module_list[0].minidump_module_list_index = 0
  module_list[0].version = 1
  module_list[0].crashpad_annotations["gpu-gl-context-is-virtual"] (type = 1) = 0
  module_list[0].crashpad_annotations["gr-context-type"] (type = 1) = 1
  module_list[0].crashpad_annotations["num-experiments"] (type = 1) = 36
  module_list[0].crashpad_annotations["vulkan-api-version"] (type = 1) = 1.3.240
  module_list[0].crashpad_annotations["egl-display-type"] (type = 1) = angle:Vulkan
  module_list[0].crashpad_annotations["gpu-gl-renderer"] (type = 1) = ANGLE (NVIDIA, Vulkan 1.3.194 (NVIDIA Quadro P1000 (0x00001CB1)), NVIDIA-510.85.2.0)
  module_list[0].crashpad_annotations["gpu-gl-vendor"] (type = 1) = Google Inc. (NVIDIA)
  module_list[0].crashpad_annotations["gpu-generation-intel"] (type = 1) = 0
  module_list[0].crashpad_annotations["gpu-vsver"] (type = 1) = 1.00
  module_list[0].crashpad_annotations["gpu-psver"] (type = 1) = 1.00
  module_list[0].crashpad_annotations["gpu-driver"] (type = 1) = 510.85.02
  module_list[0].crashpad_annotations["gpu_count"] (type = 1) = 1
  module_list[0].crashpad_annotations["gpu-devid"] (type = 1) = 0x1cb1
  module_list[0].crashpad_annotations["gpu-venid"] (type = 1) = 0x10de
  module_list[0].crashpad_annotations["switch-8"] (type = 1) = --shared-files
  module_list[0].crashpad_annotations["switch-7"] (type = 1) = --use-gl=angle
  module_list[0].crashpad_annotations["osarch"] (type = 1) = x86_64
  module_list[0].crashpad_annotations["pid"] (type = 1) = 771521
  module_list[0].crashpad_annotations["ptype"] (type = 1) = gpu-process
  module_list[0].crashpad_annotations["switch-6"] (type = 1) = --change-stack-guard-on-fork=enable
  module_list[0].crashpad_annotations["switch-5"] (type = 1) = --user-data-dir=/tmp/tmpr1y2qx1t
  module_list[0].crashpad_annotations["switch-4"] (type = 1) = --noerrdialogs
  module_list[0].crashpad_annotations["switch-3"] (type = 1) = --enable-crash-reporter=,
  module_list[0].crashpad_annotations["switch-2"] (type = 1) = --crashpad-handler-pid=771487
  module_list[0].crashpad_annotations["switch-1"] (type = 1) = --use-cmd-decoder=passthrough
  module_list[0].crashpad_annotations["num-switches"] (type = 1) = 13
  address_mask = 0
"""
    # pylint: enable=line-too-long

  def testGetCrashpadAnnotationValidNameNoType(self):
    self.assertEqual(
        minidump_utils.GetCrashpadAnnotation('', 'gpu-devid'), '0x1cb1')

  def testGetCrashpadAnnotationValidNameSpecificType(self):
    self.assertEqual(minidump_utils.GetCrashpadAnnotation('', 'switch-1', 1),
                     '--use-cmd-decoder=passthrough')

  def testGetCrashpadAnnotationValidNameWrongType(self):
    self.assertEqual(
        minidump_utils.GetCrashpadAnnotation('', 'switch-1', 2), None)

  def testGetCrashpadAnnotationInvalidName(self):
    self.assertEqual(minidump_utils.GetCrashpadAnnotation('', 'asdf'), None)

  def testGetProcessTypeFromMinidump(self):
    self.assertEqual(
        minidump_utils.GetProcessTypeFromMinidump(''), 'gpu-process')
