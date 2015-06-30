#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Makes sure that all files contain proper licensing information.'''


import json
import optparse
import os.path
import subprocess
import sys

import logging

def PrintUsage():
  print '''Usage: python checklicenses.py [--root <root>] [tocheck]
  --root   Specifies the repository root. This defaults to '../..' relative
           to the script file. This will be correct given the normal location
           of the script in '<root>/tools/checklicenses'.

  tocheck  Specifies the directory, relative to root, to check. This defaults
           to '.' so it checks everything.

Examples:
  python checklicenses.py
  python checklicenses.py --root ~/chromium/src third_party'''


WHITELISTED_LICENSES = [
    'Apache (v2.0)',
    'BSD (3 clause)',
    'BSD-like',
    'MIT/X11 (BSD like)',
    'zlib/libpng',
]


PATH_SPECIFIC_WHITELISTED_LICENSES = {
    'tracing/third_party/devscripts': [
        'GPL (v2 or later)',
    ],
}


def check_licenses(base_directory, target_directory=None):
  # Figure out which directory we have to check.
  if not target_directory:
    # No directory to check specified, use the repository root.
    start_dir = base_directory
  else:
    # Directory specified. Start here. It's supposed to be relative to the
    # base directory.
    start_dir = os.path.abspath(os.path.join(base_directory, target_directory))

  logging.info('Using base directory: %s' % base_directory)
  logging.info('Checking: %s' % start_dir)
  logging.info('')

  licensecheck_path = os.path.abspath(os.path.join(base_directory,
                                                   'tracing',
                                                   'third_party',
                                                   'devscripts',
                                                   'licensecheck.pl'))

  licensecheck = subprocess.Popen([licensecheck_path,
                                   '-l', '100',
                                   '-r', start_dir],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
  stdout, stderr = licensecheck.communicate()
  logging.info('----------- licensecheck stdout -----------')
  logging.info(stdout)
  logging.info('--------- end licensecheck stdout ---------')
  if licensecheck.returncode != 0 or stderr:
    print '----------- licensecheck stderr -----------'
    print stderr
    print '--------- end licensecheck stderr ---------'
    return 1

  used_suppressions = set()
  errors = []

  for line in stdout.splitlines():
    filename, license = line.split(':', 1)
    filename = os.path.relpath(filename.strip(), base_directory)

    # All files in the build output directory are generated one way or another.
    # There's no need to check them.
    if filename.startswith('out/'):
      continue

    # For now we're just interested in the license.
    license = license.replace('*No copyright*', '').strip()

    # Skip generated files.
    if 'GENERATED FILE' in license:
      continue

    if license in WHITELISTED_LICENSES:
      continue

    matched_prefixes = [
        prefix for prefix in PATH_SPECIFIC_WHITELISTED_LICENSES
        if filename.startswith(prefix) and
        license in PATH_SPECIFIC_WHITELISTED_LICENSES[prefix]]
    if matched_prefixes:
      used_suppressions.update(set(matched_prefixes))
      continue

    errors.append({'filename': filename, 'license': license})

  if errors:
    for error in errors:
      print "'%s' has non-whitelisted license '%s'" % (
          error['filename'], error['license'])
    print '\nFAILED\n'
    print 'Please read',
    print 'http://www.chromium.org/developers/adding-3rd-party-libraries'
    print 'for more info how to handle the failure.'
    print
    print 'Please respect OWNERS of checklicenses.py. Changes violating'
    print 'this requirement may be reverted.'

    # Do not print unused suppressions so that above message is clearly
    # visible and gets proper attention. Too much unrelated output
    # would be distracting and make the important points easier to miss.

    return 1


  return 0


def main():
  default_root = os.path.abspath(
      os.path.join(os.path.dirname(__file__), '..'))
  option_parser = optparse.OptionParser()
  option_parser.add_option('--root', default=default_root,
                           dest='base_directory',
                           help='Specifies the repository root. This defaults '
                           "to '..' relative to the script file, which "
                           'will normally be the repository root.')
  options, args = option_parser.parse_args()

  target_directory = None
  if len(args) == 1:
    target_directory = args[0]
  elif len(args) > 1:
    PrintUsage()
    return 1
  results = check_licenses(options.base_directory, target_directory)
  if not results:
    print 'SUCCESS'
  return results


if '__main__' == __name__:
  sys.exit(main())
