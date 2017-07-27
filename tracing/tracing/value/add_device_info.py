# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing.value import histogram
from tracing.value.diagnostics import reserved_infos

def AddDeviceInfo(histogram_set, chrome_version, os_name, os_version,
                  gpu_info, arch, ram):
  """Adds a shared diagnostics containing pieces of device information to a
     HistogramSet.

  Args:
    histograms_json_filename: a HistogramSet to add the diagnostics to.
    chrome_version: name of the device's Chrome version.
    os_name: name of the device's OS.
    os_version: name of the device's OS version.
    gpu_info: GPU information of the device
    arch: name of the device's OS architecture.
    ram: device's total available ram.
  """
  device_info = {
      reserved_infos.PRODUCT_VERSIONS.name: chrome_version,
      reserved_infos.OS_NAMES.name: os_name,
      reserved_infos.OS_VERSIONS.name: os_version,
      reserved_infos.GPUS.name: gpu_info,
      reserved_infos.ARCHITECTURES.name: arch,
      reserved_infos.MEMORY_AMOUNTS.name: ram,
  }

  for device_info_name, device_info_value in device_info.iteritems():
    histogram_set.AddSharedDiagnostic(
        device_info_name, histogram.GenericSet(device_info_value))
