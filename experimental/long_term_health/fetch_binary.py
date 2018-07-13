#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for downloading different versions of Chrome.

"""

import argparse
import os
import subprocess
import sys


PROCESSOR_ARCHITECTURE = 'arm'
CHROME_TYPE = 'Stable'
DEFAULT_DOWNLOAD_PATH = 'out'


class CloudDownloadFailed(Exception):
  pass


def DownloadAPKFromURI(uri, output_dir):
  """Used to download the APKs from google cloud into the out folder.

  Args:
    uri: Gsutil URI
    output_dir: The path that the APKs will be stored
  """
  def GetAPKName(gs_uri):
    # example `gs_uri`: gs://chrome-signed/android-B0urB0N/
    # 56.0.2924.3/arm/ChromeStable.apk
    return '_'.join(gs_uri.split('/')[-3:])

  # TODO(wangge): How to fail back if the download is not successful?
  try:
    subprocess.call(['gsutil', 'cp', uri,
                     os.path.join(output_dir, GetAPKName(uri))])
  except subprocess.CalledProcessError:
    raise CloudDownloadFailed(uri)


def GetLatestVersionURI(milestone_num):
  """Helper function for `GetCloudStorageURIs`.

  Args:
    milestone_num: Number representing the milestone.

  Returns:
    The URI for the latest version of Chrome for a given milestone.
  """
  subdirectory_name = 'B0urB0N' if milestone_num > 44 else 'C4MPAR1'
  # 'C4MPAR1' is used to store milestone 27 to milestone 44,
  # B0urB0N is used to store versions from milestone 45 onwards
  try:
    all_uris = subprocess.check_output(
        ['gsutil', 'ls', 'gs://chrome-signed/android-%s/%s*/%s/Chrome%s.apk' %
         (subdirectory_name, milestone_num, PROCESSOR_ARCHITECTURE, CHROME_TYPE)
        ])
  except subprocess.CalledProcessError:
    raise CloudDownloadFailed(milestone_num)

  uris = all_uris.strip().splitlines()
  # assuming that the last uri is the latest one
  return uris[-1]


def IsGsutilInstalled():
  return subprocess.call(['which', 'gsutil']) == 0


def main(args):
  if not IsGsutilInstalled():
    return 'gsutil is not installed, please install it and try again'

  parser = argparse.ArgumentParser(
      description='tool to download different versions of chrome')
  parser.add_argument('from_milestone', type=int,
                      help='starting milestone number')
  parser.add_argument('to_milestone', type=int,
                      help='ending milestone number')
  parser.add_argument('--output-path', default=DEFAULT_DOWNLOAD_PATH,
                      help='the path that the APKs well be stored')
  args = parser.parse_args(args)

  print ('Getting the storage URI, this process might '
         'take some time, please wait patiently')

  try:
    for milestone in range(args.from_milestone, args.to_milestone + 1):
      uri = GetLatestVersionURI(milestone)
      DownloadAPKFromURI(uri, args.output_path)
    return 0
  except KeyboardInterrupt:
    return 'interrupted, exiting...'
  # TODO(wangge): do we need to catch other type of exception


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
