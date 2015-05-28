# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for catapult.

See https://www.chromium.org/developers/how-tos/depottools/presubmit-scripts
for more details about the presubmit API built into depot_tools.
"""


def GetPreferredTryMasters(project, change):
  return {
    'tryserver.client.catapult': {
      'Catapult Linux Tryserver': set(['defaulttests']),
      'Catapult Mac Tryserver': set(['defaulttests']),
      'Catapult Windows Tryserver': set(['defaulttests']),
    }
  }