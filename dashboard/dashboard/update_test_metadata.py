# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Updates the metadata for tests from descriptions in Chromium source.

TODO(qyearsley): Remove this request handler when units are updated from
    metadata that is sent along with test results.
"""

import base64
import binascii
import json
import logging

from google.appengine.api import urlfetch

from dashboard import request_handler
from dashboard import units_to_direction

# Paths to the unit and test description metadata files in chromium/src.
_UNIT_JSON_PATH = 'tools/telemetry/telemetry/value/unit-info.json'


class UpdateTestMetadataHandler(request_handler.RequestHandler):
  """URL endpoint for updating tests from metadata in chromium source.

  Intended to be called via a cron job, but can be updated by hand by an
  administrator (by navigating to the /update_test_metadata endpoint.)
  """

  def get(self):
    """Same as post. Parameters can also be given in the query string."""
    self.post()

  def post(self):
    """Updates the test metadata.

    Outputs:
      Nothing if successful, an error message if there was an error.
    """
    units_data = _GetAndParseChromiumJsonFile(_UNIT_JSON_PATH)
    if units_data:
      units_to_direction.UpdateFromJson(units_data)
    else:
      self.ReportError('Could not fetch or parse unit data.')


def _GetAndParseChromiumJsonFile(path):
  """Fetches and parses JSON file in the chromium/src repository."""
  downloaded_json = DownloadChromiumFile(path)
  if not downloaded_json:
    return None
  try:
    return json.loads(downloaded_json)
  except ValueError:
    logging.error('Failed to load JSON "%s" from "%s".', downloaded_json, path)
    return None


def DownloadChromiumFile(path):
  """Downloads a file in the chromium/src repository.

  This function uses gitiles to fetch files. As of August 2014, gitiles
  doesn't seem to support fetching files as plain text, but supports
  fetching base-64 encodings of files, so we use that.  used. If it
  supports fetching plain text in the future, that could also be used,
  and may be simpler.

  Args:
    path: Path to a file in src repository, without a leading slash or "src/".

  Returns:
    The contents of the file as a string or None on failure.
  """
  base_url = 'https://chromium.googlesource.com/chromium/src/+/master/'
  url = '%s%s?format=TEXT' % (base_url, path)
  response = urlfetch.fetch(url)
  if response.status_code != 200:
    logging.error('Got %d fetching "%s".', response.status_code, url)
    return None
  try:
    plaintext_content = base64.decodestring(response.content)
  except binascii.Error:
    logging.error('Failed to decode "%s" from "%s".', response.content, url)
    return None
  return plaintext_content
