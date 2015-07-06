# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for catapult.

See https://www.chromium.org/developers/how-tos/depottools/presubmit-scripts
for more details about the presubmit API built into depot_tools.
"""


def GetPreferredTryMasters(project, change):  # pylint: disable=unused-argument
  return {
      'tryserver.client.catapult': {
          'Catapult Linux Tryserver': {'defaulttests'},
          'Catapult Mac Tryserver': {'defaulttests'},
          'Catapult Windows Tryserver': {'defaulttests'},
      }
  }


def _CommonChecks(input_api, output_api):
  results = []
  results.extend(input_api.canned_checks.PanProjectChecks(
      input_api, output_api))
  return results


def CheckChangeOnUpload(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results


def CheckChangeOnCommit(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results
