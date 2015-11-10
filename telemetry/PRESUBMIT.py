# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


def _LicenseHeader(input_api):
  """Returns the license header regexp."""
  # Accept any year number from 2011 to the current year
  current_year = int(input_api.time.strftime('%Y'))
  allowed_years = (str(s) for s in reversed(xrange(2011, current_year + 1)))
  years_re = '(' + '|'.join(allowed_years) + ')'
  license_header = (
      r'.*? Copyright %(year)s The Chromium Authors\. All rights reserved\.\n'
      r'.*? Use of this source code is governed by a BSD-style license that '
      r'can be\n'
      r'.*? found in the LICENSE file.\n') % {'year': years_re}
  return license_header


def _CheckLicense(input_api, output_api):
  results = input_api.canned_checks.CheckLicense(
      input_api, output_api, _LicenseHeader(input_api))
  if results:
    results.append(
        output_api.PresubmitError('License check failed. Please fix.'))
  return results


def _CommonChecks(input_api, output_api):
  results = []

  results.extend(_CheckLicense(input_api, output_api))
  results.extend(input_api.RunTests(input_api.canned_checks.GetPylint(
      input_api, output_api, extra_paths_list=_GetPathsToPrepend(input_api),
      pylintrc='pylintrc')))
  results.extend(_CheckNoMoreUsageOfDeprecatedCode(
    input_api, output_api, deprecated_code='GetChromiumSrcDir()',
    crbug_number=511332))
  return results


def _CheckNoMoreUsageOfDeprecatedCode(
    input_api, output_api, deprecated_code, crbug_number):
  results = []
  # These checks are not perfcet but should be good enough for most of our
  # usecases.
  def _IsAddedLine(line):
    return line.startswith('+') and not line.startswith('+++ ')
  def _IsRemovedLine(line):
    return line.startswith('-') and not line.startswith('--- ')

  presubmit_dir = input_api.os_path.join(
      input_api.PresubmitLocalPath(), 'PRESUBMIT.py')

  added_calls = 0
  removed_calls = 0
  for affected_file in input_api.AffectedFiles():
    # Do not do the check on PRESUBMIT.py itself.
    if affected_file.AbsoluteLocalPath() == presubmit_dir:
      continue
    for line in affected_file.GenerateScmDiff().splitlines():
      if _IsAddedLine(line) and deprecated_code in line:
        added_calls += 1
      elif _IsRemovedLine(line) and deprecated_code in line:
        removed_calls += 1

  if added_calls > removed_calls:
    results.append(output_api.PresubmitError(
        'Your patch adds more instances of %s. Please see crbug.com/%i for'
        'how to proceed.' % (deprecated_code, crbug_number)))
  return results


def _GetPathsToPrepend(input_api):
  telemetry_dir = input_api.PresubmitLocalPath()
  chromium_src_dir = input_api.os_path.join(telemetry_dir, '..', '..')
  return [
      telemetry_dir,
      input_api.os_path.join(telemetry_dir, 'third_party', 'altgraph'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'mock'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'modulegraph'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'pexpect'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'png'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'pyfakefs'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'pyserial'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'typ'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'webpagereplay'),
      input_api.os_path.join(telemetry_dir, 'third_party', 'websocket-client'),

      input_api.os_path.join(chromium_src_dir, 'build', 'android'),
      input_api.os_path.join(chromium_src_dir,
                             'third_party', 'catapult', 'tracing'),
  ]


def CheckChangeOnUpload(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results


def CheckChangeOnCommit(input_api, output_api):
  results = []
  results.extend(_CommonChecks(input_api, output_api))
  return results
