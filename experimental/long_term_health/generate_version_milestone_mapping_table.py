#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for generating the full_milestone_info.csv.

"""

import csv
import datetime
import httplib
import json
import os
import re


USELESS_CHAR_COUNT = 5
APP_DIR = os.path.normpath(os.path.dirname(__file__))


class MappingGenerationFailed(Exception):
  pass


def GetChromiumLog(revision, count=10):
  """Used to get the git commit log for the given revision.

  Args:
    revision: the revision that you want the git log for
    count: the number of git logs that you want to get back
  Returns:
    list: a list of git logs
  """
  conn = httplib.HTTPSConnection('chromium.googlesource.com')
  conn.request('GET', '/chromium/src.git/+log'
                      '/%s?format=JSON&n=%s' % (revision, count))
  response = conn.getresponse()
  # we skip the useless character at the front of the json
  # that is sent back to us
  return json.loads(response.read()[USELESS_CHAR_COUNT:])['log']


def GetBranchInfo(milestone, branch):
  """Get the latest version number and release date for a given branch.

  Args:
    milestone: the major version number
    branch: the latest branch corresponding with the milestone

  Returns:
    dict: version incrementing log info

  Raises:
    MappingGenerationFailed: this would be raised if
      no log is incrementing the version
  """
  # loop through the logs to get the first log
  # that increments the version number
  for log in GetChromiumLog('refs/branch-heads/%s' % branch):
    version_number = re.search(
        r'(?<=Incrementing VERSION to )[\d.]+', log['message'])
    if version_number:
      release_date = datetime.datetime.strptime(
          log['committer']['time'], '%a %b %d %X %Y').isoformat()
      return (milestone, branch, version_number.group(0), release_date)

  #  raise exception if non of the log is relevant
  assert False, 'Could not find commit with version increment'


def main():
  with open(os.path.join(APP_DIR, 'full_milestone_info.csv'), 'w') as new_table:
    writer = csv.writer(new_table)
    writer.writerow(['milestone', 'branch', 'version_number', 'release_date'])
    with open(os.path.join(
        APP_DIR, 'milestone_build_mapping_table.csv')) as milestone_build_table:
      reader = csv.reader(milestone_build_table)
      next(reader, None)  # skip the header line
      for milestone, branch in reader:
        writer.writerow(GetBranchInfo(milestone, branch))


if __name__ == '__main__':
  main()
