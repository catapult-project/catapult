# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Class and functions for generating the full milestone info table.
"""
import csv
import datetime
import httplib
import json
import os
import re
import subprocess

from long_term_health import utils

USELESS_CHAR_COUNT = 5
PROCESSOR_ARCHITECTURE = 'arm'


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
  """Generate Full info csv from milestone_build_mapping_table.
  """
  with open(os.path.join(
      utils.APP_ROOT, 'full_milestone_info.csv'), 'w') as new_table:
    writer = csv.writer(new_table)
    writer.writerow(['milestone', 'branch', 'version_number', 'release_date'])
    with open(os.path.join(
        utils.APP_ROOT, 'milestone_build_mapping_table.csv'
    )) as milestone_build_table:
      reader = csv.reader(milestone_build_table)
      next(reader, None)  # skip the header line
      for milestone, branch in reader:
        writer.writerow(GetBranchInfo(milestone, branch))


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
            'release_date': utils.ParseIsoFormatDate(row['release_date'])
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

    raise utils.CloudDownloadFailed(milestone_num)

