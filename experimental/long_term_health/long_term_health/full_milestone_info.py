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

from long_term_health import utils

USELESS_CHAR_COUNT = 5


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
    tuple(string): milestone number, branch, version number, and release date
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

  def GetLatestMilestoneBeforeDate(self, date):
    for row in reversed(self._table):
      if row['release_date'] < date:
        return row['milestone']
    raise LookupError(
        'Cannot find any version before the given date %s' % date.isoformat())

  def GetEarliestMilestoneAfterDate(self, date):
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
