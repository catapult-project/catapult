# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import tracing_project
import vinn

_ADD_SHARED_DIAGNOSTIC_CMD_LINE = os.path.join(
    os.path.dirname(__file__), 'add_shared_diagnostic_cmdline.html')


def AddSharedDiagnostic(
    histograms_json_filename, diagnostic_name, diagnostic_filename):
  """Add a shared Diagnostic to a set of histograms.

  Args:
    histograms_json_filename: path to a histograms JSON file.
    diagnostic_name: name of diagnostic to add.
    diagnostic_filename: path to a diagnostic JSON file.
  Returns:
    Vinn result containing the new histograms JSON with added shared diagnostic.
  """
  project = tracing_project.TracingProject()
  all_source_paths = list(project.source_paths)
  return vinn.RunFile(
      _ADD_SHARED_DIAGNOSTIC_CMD_LINE,
      source_paths=all_source_paths,
      js_args=[
          os.path.abspath(histograms_json_filename),
          diagnostic_name,
          os.path.abspath(diagnostic_filename),
      ])
