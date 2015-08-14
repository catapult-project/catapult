# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def _CommonChecks(input_api, output_api):
  results = []

  # TODO(nduca): This should call update_docs.IsUpdateDocsNeeded().
  # Disabled due to crbug.com/255326.
  if False:
    update_docs_path = input_api.os_path.join(
      input_api.PresubmitLocalPath(), 'update_docs')
    assert input_api.os_path.exists(update_docs_path)
    results.append(output_api.PresubmitError(
      'Docs are stale. Please run:\n' +
      '$ %s' % input_api.os_path.abspath(update_docs_path)))

  pylint_checks = input_api.canned_checks.GetPylint(
    input_api, output_api, extra_paths_list=_GetPathsToPrepend(input_api),
    pylintrc='pylintrc')

  results.extend(input_api.RunTests(pylint_checks))
  return results


def _GetPathsToPrepend(input_api):
  telemetry_dir = input_api.PresubmitLocalPath()
  chromium_src_dir = input_api.os_path.join(telemetry_dir, '..', '..')
  return [
      telemetry_dir,
      input_api.os_path.join(telemetry_dir, 'third_party', 'mock'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'typ'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'websocket-client'),

      input_api.os_path.join(chromium_src_dir, 'build', 'android'),
      input_api.os_path.join(chromium_src_dir, 'third_party', 'catapult'),
      input_api.os_path.join(chromium_src_dir, 'third_party', 'webpagereplay'),
  ]


def CheckChangeOnUpload(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results


def CheckChangeOnCommit(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results
