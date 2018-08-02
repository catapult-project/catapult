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
# pylint: disable=import-error
# pylint: disable=no-name-in-module
from distutils.version import LooseVersion


PROCESSOR_ARCHITECTURE = 'arm'
DEFAULT_DOWNLOAD_PATH = 'out'
APP_DIR = os.path.normpath(os.path.dirname(__file__))
USELESS_CHAR_COUNT = 5


class CloudDownloadFailed(Exception):
  pass


def ParseIsoFormatDate(iso_date_str):
  return datetime.datetime.strptime(iso_date_str, '%Y-%m-%dT%H:%M:%S')


def ParseDate(date_str):
  """Convert a formatted date string to a datetime object.

  Args:
    date_str(string): a date string in the format `2018-10-01`

  Returns:
    Datetime: corresponding object representing the date_str

  Raises:
    argparse.ArgumentTypeError: it will be risen if the date string cannot be
      converted to Datetime object
  """
  try:
    date_object = datetime.datetime.strptime(date_str, '%Y-%m-%d')
  except ValueError:
    msg = (
        '%s is not a valid date value or it doesn\'t adhere to the required '
        'format, please double check' % date_str)
    raise argparse.ArgumentTypeError(msg)
  return date_object


def ColoredStr(string):
  class Colors(object):
    OKGREEN = '\033[92m'
    ENDC = '\033[0m'

  return Colors.OKGREEN + string + Colors.ENDC


class MilestoneInfo(object):
  """Simple class to store the full_milestone_info.csv data.
  """

  def __init__(self, path_to_full_info_table):
    self._table = list(self._LoadCsvTable(path_to_full_info_table))
    assert self._table, "full_milestone_info.csv doesn't have any rows"

  def _LoadCsvTable(self, path_to_full_info_table):
    with open(path_to_full_info_table) as f:
      for row in csv.DictReader(f):
        yield {
            'milestone': int(row['milestone']),
            'branch': int(row['branch']),
            'version_number': row['version_number'],
            'release_date': ParseIsoFormatDate(row['release_date'])
        }

  @property
  def latest_milestone(self):
    return self._table[-1]['milestone']

  def GetLatestVersionBeforeDate(self, date):
    for row in reversed(self._table):
      if row['release_date'] < date:
        return row['milestone']

    raise LookupError(
        'Cannot find any version before the given date %s' % date.isoformat())

  def GetEarliestVersionAfterDate(self, date):
    for row in self._table:
      if row['release_date'] > date:
        return row['milestone']
    raise LookupError(
        'Cannot find any version after the given date %s' % date.isoformat())

  def GetVersionNumberFromMilestone(self, target_milestone):
    for row in self._table:
      if target_milestone == row['milestone']:
        return row['version_number']
    raise LookupError('Cannot find version the number for the milestone %s' %
                      target_milestone)

  def GetLatestVersionURI(self, milestone_num):
    """Get the latest google cloud storage uri for given milestone.

    Args:
      milestone_num(int): Number representing the milestone.

    Returns:
      string: The URI for the latest version of Chrome for a given milestone.

    Raises:
      CloudDownloadFailed: this would be risen if we cannot find the apk within
      5 patches
    """
    version_num = self.GetVersionNumberFromMilestone(milestone_num)
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
      return milestone, branch, version_number.group(0), release_date

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

  Returns:
    string: the path of the downloaded APK
  """

  def GetAPKName(gs_uri):
    # example `gs_uri`: gs://chrome-signed/android-B0urB0N/56.0.2924.3/arm/
    # ChromeStable.apk
    return '_'.join(gs_uri.split('/')[-3:])

  path_to_apk = os.path.join(output_dir, GetAPKName(uri))

  try:
    subprocess.check_call(['gsutil', 'cp', uri, path_to_apk])
  except subprocess.CalledProcessError:
    raise CloudDownloadFailed(uri)

  return path_to_apk


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
  assert int(version_num_list[-1]) >= 0, 'patch number cannot be negative'
  return '.'.join(version_num_list)


def BuildArgumentParser(args):
  """Set the expected options for the argument parser.

  If the program is ran with no argument, it will download the 10 latest
  chrome versions

  Args:
    args(list): list of arguments(string)

  Returns:
    Namespace: a class storing all the parsed arguments
  """
  parser = argparse.ArgumentParser(
      description='tool to download different versions of chrome')
  # from_date and from_milestone cannot present at the same time
  start = parser.add_mutually_exclusive_group()
  # to_date and to_milestone cannot present at the same time
  end = parser.add_mutually_exclusive_group()
  start.add_argument('--from-milestone', type=int,
                     help='starting milestone number')
  start.add_argument('--from-date', type=ParseDate,
                     help='starting version release date'
                          ', must be in the format `2017-10-02`')
  end.add_argument('--to-milestone', type=int,
                   help='ending milestone number')
  end.add_argument('--to-date', type=ParseDate,
                   help='ending version release date'
                        ', must be in the format `2017-10-02`')
  parser.add_argument('--output-path', default=DEFAULT_DOWNLOAD_PATH,
                      help='the path that the APKs will be stored')
  return parser.parse_args(args)


def ProcessArguments(args, milestone_info):
  """Set `to_milestone` and `from_milestone` according to provided arguments.

  Args:
    args(Namespace class): object storing the relevant arguments
    milestone_info(MilestoneInfo class): the object that stores all the table
        content
  """
  if args.from_date:
    args.from_milestone = milestone_info.GetEarliestVersionAfterDate(
        args.from_date)
  if args.to_date:
    args.to_milestone = milestone_info.GetLatestVersionBeforeDate(args.to_date)
  if args.from_milestone is None:
    args.from_milestone = milestone_info.latest_milestone - 9
  if args.to_milestone is None:
    args.to_milestone = milestone_info.latest_milestone


def GetLocalAPK(milestone_num, output_path):
  """Get the local path of the APK for the given milestone.

  Args:
    milestone_num(int): the milestone number
    output_path(string): the directory that the apks will be downloaded in

  Returns:
    string/None: returns None if there is no local apk, returns path otherwise
  """
  def ParseVersion(apk_name):
    return LooseVersion(apk_name.split('_')[0])

  if not os.path.isdir(output_path):
    return None

  local_apks = sorted([apk for apk in os.listdir(
      output_path) if apk.startswith('%d.' % milestone_num)], key=ParseVersion)
  return None if not local_apks else os.path.join(output_path, local_apks[-1])


def GetAPK(milestone_num, output_path, milestone_info):
  """Get the path to an APK, download if it doesn't exist.

  Args:
    milestone_num(int): milestone number
    output_path(string): the directory that the apks will be downloaded in
    milestone_info(MilestoneInfo):

  Returns:
    string: the path to the apk for the given milestone
  """
  local_apk_path = GetLocalAPK(milestone_num, output_path)
  if local_apk_path is None:
    uri = milestone_info.GetLatestVersionURI(milestone_num)
    return DownloadAPKFromURI(uri, output_path)
  return local_apk_path


def RunBenchmark(path_to_apk):
  """Install the APK and run the benchmark on it.

  Args:
    path_to_apk(string): the *relative* path to the APK
  """
  apk_name = path_to_apk.split('/')[-1]
  subprocess.call(['adb', 'install', '-r', '-d', path_to_apk])
  subprocess.call(['../../../../tools/perf/run_benchmark',
                   '--browser=android-system-chrome',
                   '--pageset-repeat=1',  # could remove this later
                   '--results-label=%s' % apk_name,  # could remove this as well
                   # TODO(wangge):not sure if we should run in compatibility
                   # mode even for the later version, probably add a check in
                   # caller to determine if we should run it in compatibility
                   # mode and add an argument `run_in_compatibility_mode` to
                   # the `RunBenchmark` function
                   '--compatibility-mode',
                   '--story-filter=wikipedia',  # could remove this
                   # thinking of adding an argument to the tool to set this
                   '--output-dir=%s' % os.path.join(
                       APP_DIR, 'results', apk_name,
                       datetime.datetime.now().isoformat()),
                   # thinking of adding an argument to the tool to set this too
                   'system_health.memory_mobile'])


def main(args):
  args = BuildArgumentParser(args)

  if not IsGsutilInstalled():
    return 'gsutil is not installed, please install it and try again'

  if not os.path.isfile(os.path.join(APP_DIR, 'full_milestone_info.csv')):
    print 'Generating full milestone info table, please wait'
    GenerateFullInfoCSV()

  # load the full_milestone_info.csv into memory for later use
  milestone_info = MilestoneInfo(os.path.join(
      APP_DIR, 'full_milestone_info.csv'))
  ProcessArguments(args, milestone_info)

  try:
    for milestone in range(args.from_milestone, args.to_milestone + 1):
      print ColoredStr(
          'Getting the path of the APK for milestone %d.' % milestone)
      path_to_apk = GetAPK(milestone, args.output_path, milestone_info)
      print ColoredStr('Running benchmark for milestone %d:' % milestone)
      RunBenchmark(path_to_apk)

    return 0
  except KeyboardInterrupt:
    return 'interrupted, exiting...'
  # TODO(wangge): do we need to catch other type of exception


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
