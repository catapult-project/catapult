# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import tempfile

from tracing.value import add_shared_diagnostic

def AddDeviceInfo(histograms_json_filename, chrome_version, os_name, os_version,
                  gpu_info, arch, ram):
  device_info = {
      'chromeVersion': chrome_version,
      'osName': os_name,
      'osVersion': os_version,
      'gpuInfo': gpu_info,
      'arch': arch,
      'ram': ram,
  }

  with tempfile.NamedTemporaryFile() as diagnostic_file:
    json.dump(device_info, diagnostic_file)
    return add_shared_diagnostic.AddSharedDiagnostic(
        histograms_json_filename, 'device', diagnostic_file.name)
