# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import tempfile

from tracing.value import add_shared_diagnostic

def AddRevisionInfo(histograms_json_filename, chromium, v8, catapult, angle,
                    skia, webrtc):
  revision_info = {
      'chromium': chromium,
      'v8': v8,
      'catapult': catapult,
      'angle': angle,
      'skia': skia,
      'webrtc': webrtc,
  }

  with tempfile.NamedTemporaryFile() as diagnostic_file:
    json.dump(revision_info, diagnostic_file)
    return add_shared_diagnostic.AddSharedDiagnostic(
        histograms_json_filename, 'revisions', diagnostic_file.name)
