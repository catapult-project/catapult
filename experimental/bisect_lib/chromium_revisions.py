# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import urllib2

BASE_URL = 'https://chromium.googlesource.com/chromium/src/+'
PADDING = ')]}\'\n'  # Gitiles padding.

def revision_info(revision):
  """Gets information about a chromium revision.

  Args:
    revision (str): The git commit hash of the revision to check.

  Returns:
    A dictionary containing the author, email, 'subject' (the first line of the
    commit message) the 'body' (the whole message) and the date in string format
    like "Sat Oct 24 00:33:21 2015".
  """

  url = '%s/%s?format=json' % (BASE_URL, revision)
  response = urllib2.urlopen(url).read()
  response = json.loads(response[len(PADDING):])
  message = response['message'].splitlines()
  subject = message[0]
  body = '\n'.join(message[1:])
  result = {
      'author': response['author']['name'],
      'email': response['author']['email'],
      'subject': subject,
      'body': body,
      'date': response['committer']['time'],
  }
  return result


def revision_range(first_revision, last_revision):
  """Gets the revisions in chromium between first and last including the latter.

  Args:
    first_revision (str): The git commit of the first revision in the range.
    last_revision (str): The git commit of the last revision in the range.

  Returns:
    A list of dictionaries, one for each revision after the first revision up to
    and including the last revision. For each revision, its dictionary will
    contain information about the author and the comitter and the commit itself
    analogously to the 'git log' command. See test_data/MOCK_RANGE_RESPONSE_FILE
    for an example.
  """
  url = '%slog/%s..%s?format=json' % (BASE_URL, first_revision, last_revision)
  response = urllib2.urlopen(url).read()
  response = json.loads(response[len(PADDING):])
  return response['log']
