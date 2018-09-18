# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import urllib

import httplib2

from py_utils import retry_util  # pylint: disable=import-error


class RequestError(OSError):
  """Exception class for errors while making a request."""
  def __init__(self, request, response, content):
    self.request = request
    self.response = response
    self.content = content
    super(RequestError, self).__init__(
        '%s returned HTTP Error %d: %s' % (
            self.request, self.response.status, self.error_message))

  def __reduce__(self):
    # Method needed to make the exception pickleable [1], otherwise it causes
    # the mutliprocess pool to hang when raised by a worker [2].
    # [1]: https://stackoverflow.com/a/36342588
    # [2]: https://github.com/uqfoundation/multiprocess/issues/33
    return (type(self), (self.request, self.response, self.content))

  @property
  def json(self):
    try:
      return json.loads(self.content)
    except StandardError:
      return None

  @property
  def error_message(self):
    try:
      # Try to find error message within json content.
      return self.json['error']
    except StandardError:
      # Otherwise fall back to entire content itself.
      return self.content


class ClientError(RequestError):
  """Exception for 4xx HTTP client errors."""
  pass


class ServerError(RequestError):
  """Exception for 5xx HTTP server errors."""
  pass


def BuildRequestError(request, response, content):
  """Build the correct RequestError depending on the response status."""
  if response['status'].startswith('4'):
    error = ClientError
  elif response['status'].startswith('5'):
    error = ServerError
  else:  # Fall back to the base class.
    error = RequestError
  return error(request, response, content)


@retry_util.RetryOnException(ServerError, retries=3)
def Request(url, params=None, credentials=None, retries=None):
  del retries  # Handled by the decorator.

  if params:
    url = '%s?%s' % (url, urllib.urlencode(params))

  http = httplib2.Http()
  if credentials is not None:
    if credentials.access_token_expired:
      credentials.refresh(http)
    http = credentials.authorize(http)

  logging.info('Making API request: %s', url)
  response, content = http.request(
      url, method='POST', headers={'Content-length': 0})
  if response.status != 200:
    raise BuildRequestError(url, response, content)
  return content
