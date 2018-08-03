# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Miscellaneous helper functions and variables.
"""
import argparse
import datetime
import os
import subprocess


APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))


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


def IsGsutilInstalled():
  return subprocess.call(['which', 'gsutil']) == 0


def ColoredStr(string):
  class Colors(object):
    OKGREEN = '\033[92m'
    ENDC = '\033[0m'

  return Colors.OKGREEN + string + Colors.ENDC
