# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import re
import sys
import time


def CheckCopyright(input_api):
  sources = input_api.AffectedFiles(include_deletes=False)

  project_name = 'Chromium'

  current_year = int(time.strftime('%Y'))
  allow_old_years=False
  if allow_old_years:
    allowed_years = (str(s) for s in reversed(xrange(2006, current_year + 1)))
  else:
    allowed_years = [str(current_year)]
  years_re = '(' + '|'.join(allowed_years) + ')'

  # The (c) is deprecated, but tolerate it until it's removed from all files.
  license_header = (
      r'.*? Copyright (\(c\) )?%(year)s The %(project)s Authors\. '
        r'All rights reserved\.\n'
      r'.*? Use of this source code is governed by a BSD-style license that '
        r'can be\n'
      r'.*? found in the LICENSE file\.(?: \*/)?\n'
  ) % {
      'year': years_re,
      'project': project_name,
  }
  license_re = re.compile(license_header, re.MULTILINE)
  bad_files = []
  for f in sources:
    contents = f.contents
    if not license_re.search(contents):
      bad_files.append(f.filename)
  if bad_files:
    return [
        'License must match:\n%s\n' % license_re.pattern +
        'Found a bad license header in these files:\n' +
        '\n'.join(['  ' + x for x in bad_files])
    ]
  return []


def RunChecks(input_api):
  results = []
  results += CheckCopyright(input_api)
  return results

