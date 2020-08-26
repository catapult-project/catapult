# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""URL endpoint for getting information about histogram upload proccess."""
from __future__ import absolute_import

import logging

from dashboard.api import api_request_handler
from dashboard.models import upload_completion_token


class UploadInfoHandler(api_request_handler.ApiRequestHandler):
  """Request handler to get information about upload completion tokens."""

  def _CheckUser(self):
    self._CheckIsInternalUser()

  def _GenerateResponse(self, token, measurements=None):
    measurements = measurements or []
    result = {
        'token': token.key.id(),
        'file': token.temporary_staging_file_path,
        'created': str(token.creation_time),
        'lastUpdated': str(token.update_time),
        'state': upload_completion_token.StateToString(token.state),
    }
    if measurements:
      result['measurements'] = []
    for measurement in measurements:
      result['measurements'].append({
          'name': measurement.key.id(),
          'state': upload_completion_token.StateToString(measurement.state),
      })
    return result

  def Get(self, *args):
    """Returns json, that describes state of the token.

    Can be called by get request to /uploads/<token_id>.

    Response is json of the form:
    {
      "token": "...",
      "file": "...",
      "created": "...",
      "lastUpdated": "...",
      "state": "PENDING|PROCESSING|FAILED|COMPLETED",
      "measurements": [
        {
          "name": "...",
          "state": "PROCESSING|FAILED|COMPLETED",
        },
        ...
      ]
    }
    Description of the fields:
      - token: Token id from the request.
      - file: Temporary staging file path, where /add_histogram request data is
        stored during the PENDING stage. For more information look at
        /add_histogram api.
      - created: Date and time of creation.
      - lastUpdated: Date and time of last update.
      - state: Aggregated state of the token and all associated measurements.
      - measurements: List of jsons, that describes measurements, associated
        with the token. If there is no such measurements, the field will be
        absent.
        - name: The path  of the measurement. It is a fully-qualified path in
          the Dashboard.
        - state: State of the measurement.

    Meaning of some common error codes:
      - 403: The user is not authorized to check on the status of an upload.
      - 404: Token could not be found. It is either expired or the token is
        invalid.
    """
    assert len(args) == 1

    token_id = args[0]
    token = upload_completion_token.Token.get_by_id(token_id)
    if token is None:
      logging.error('Upload completion token not found. Token id: %s', token_id)
      raise api_request_handler.NotFoundError

    measurements = token.GetMeasurements()
    return self._GenerateResponse(token, measurements)
