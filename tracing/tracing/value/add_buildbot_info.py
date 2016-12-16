# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import tempfile

from tracing.value import add_shared_diagnostic

def AddBuildbotInfo(histograms_json_filename, display_master, display_bot,
                    buildbot_master, buildbot, number, log):
  buildbot_info = {
      'displayMasterName': display_master,
      'displayBotName': display_bot,
      'buildbotMasterName': buildbot_master,
      'buildbotName': buildbot,
      'buildNumber': number,
      'logUri': log,
  }

  with tempfile.NamedTemporaryFile() as diagnostic_file:
    json.dump(buildbot_info, diagnostic_file)
    return add_shared_diagnostic.AddSharedDiagnostic(
        histograms_json_filename, 'buildbot', diagnostic_file.name)
