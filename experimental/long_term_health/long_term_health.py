#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for downloading different versions of Chrome.

"""

import argparse
import csv
import datetime
import httplib
import json
import os
import re
import subprocess
import sys


PROCESSOR_ARCHITECTURE = 'arm'
DEFAULT_DOWNLOAD_PATH = 'out'
APP_DIR = os.path.normpath(os.path.dirname(__file__))
USELESS_CHAR_COUNT = 5


class CloudDownloadFailed(Exception):
  pass


def IsGsutilInstalled():
  return subprocess.call(['which', 'gsutil']) == 0


def GetChromiumLog(revision, count=10):
  """Used to get the git commit log for the given revision.

  Args:
    revision(string): the revision that you want the git log for
    count(int): the number of git logs that you want to get back

  Returns:
    list: a list of git logs
  """
  conn = httplib.HTTPSConnection('chromium.googlesource.com')
  conn.request('GET', '/chromium/src.git/+log'
                      '/%s?format=JSON&n=%s' % (revision, count))
  response = conn.getresponse()
  # we skip the useless characters at the front of the json that is sent back
  # to us
  return json.loads(response.read()[USELESS_CHAR_COUNT:])['log']


def GetBranchInfo(milestone, branch):
  """Get the latest version number and release date for a given branch.

  Args:
    milestone(string): the major version number
    branch(string): the latest branch corresponding with the milestone

  Returns:
    dict: version incrementing log info
  """
  # loop through the logs to get the first log that increments the version
  # number
  for log in GetChromiumLog('refs/branch-heads/%s' % branch):
    version_number = re.search(
        r'(?<=Incrementing VERSION to )[\d.]+', log['message'])
    if version_number:
      release_date = datetime.datetime.strptime(
          log['committer']['time'], '%a %b %d %X %Y').isoformat()
      return (milestone, branch, version_number.group(0), release_date)

  #  raise exception if non of the log is relevant
  assert False, 'Could not find commit with version increment'


def GenerateFullInfoCSV():
  with open(os.path.join(APP_DIR, 'full_milestone_info.csv'), 'w') as new_table:
    writer = csv.writer(new_table)
    writer.writerow(['milestone', 'branch', 'version_number', 'release_date'])
    with open(os.path.join(
        APP_DIR, 'milestone_build_mapping_table.csv')) as milestone_build_table:
      reader = csv.reader(milestone_build_table)
      next(reader, None)  # skip the header line
      for milestone, branch in reader:
        writer.writerow(GetBranchInfo(milestone, branch))


def DownloadAPKFromURI(uri, output_dir):
  """Used to download the APKs from google cloud into the out folder.

  Args:
    uri(string): Gsutil URI
    output_dir(string): The path that the APKs will be stored
  """
  def GetAPKName(gs_uri):
    # example `gs_uri`: gs://chrome-signed/android-B0urB0N/56.0.2924.3/arm/
    # ChromeStable.apk
    return '_'.join(gs_uri.split('/')[-3:])

  # TODO(wangge): How to fail back if the download is not successful?
  try:
    subprocess.check_call(['gsutil', 'cp', uri,
                           os.path.join(output_dir, GetAPKName(uri))])
  except subprocess.CalledProcessError:
    raise CloudDownloadFailed(uri)


def GetLatestVersionURI(milestone_num):
  """Helper function for `GetCloudStorageURIs`.

  Args:
    milestone_num(int): Number representing the milestone.

  Returns:
    string: The URI for the latest version of Chrome for a given milestone.

  Raises:
    CloudDownloadFailed: this would be rise if we cannot find the apk within 5
    patch
  """
  with open(os.path.join(
      APP_DIR, 'full_milestone_info.csv')) as full_info_table:
    reader = csv.reader(full_info_table)
    next(reader)  # skip the header line
    for milestone, _, version_num, _ in reader:
      if int(milestone) == milestone_num:
        # check whether the latest patch is in the Google Cloud storage as
        # sometimes it is not, so we need to decrement patch and get the
        # previous one
        for i in range(5):
          # above number has been tested, and it works from milestone 45 to 68
          download_uri = ('gs://chrome-signed/android-B0urB0N/%s/%s/Chrome'
                          'Stable.apk') % (DecrementPatchNumber(version_num, i),
                                           PROCESSOR_ARCHITECTURE)
          # check exit code to confirm the existence of the package
          if subprocess.call(['gsutil', 'ls', download_uri]) == 0:
            return download_uri

    raise CloudDownloadFailed(milestone_num)


def DecrementPatchNumber(version_num, num):
  """Helper function for `GetLatestVersionURI`.

  DecrementPatchNumber('68.0.3440.70', 6) => '68.0.3440.64'

  Args:
    version_num(string): version number to be decremented
    num(int): the amount that the patch number need to be reduced

  Returns:
    string: decremented version number
  """
  version_num_list = version_num.split('.')
  version_num_list[-1] = str(int(version_num_list[-1]) - num)
  assert version_num_list[-1] >= 0, 'patch number cannot be negative'
  return '.'.join(version_num_list)


def main(args):
  parser = argparse.ArgumentParser(
      description='tool to download different versions of chrome')
  parser.add_argument('from_milestone', type=int,
                      help='starting milestone number')
  parser.add_argument('to_milestone', type=int,
                      help='ending milestone number')
  parser.add_argument('--output-path', default=DEFAULT_DOWNLOAD_PATH,
                      help='the path that the APKs well be stored')
  args = parser.parse_args(args)

  if not IsGsutilInstalled():
    return 'gsutil is not installed, please install it and try again'

  if not os.path.isfile(os.path.join(APP_DIR, 'full_milestone_info.csv')):
    print 'Generating full milestone info table, please wait'
    GenerateFullInfoCSV()

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
