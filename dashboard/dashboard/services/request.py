# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json
import urllib

from dashboard.common import utils


def RequestJson(*args, **kwargs):
  """Fetch a URL and JSON-decode the response.

  See the documentation for Request() for details
  about the arguments and exceptions.
  """
  return json.loads(Request(*args, **kwargs))


def Request(url, method='GET', body=None, **parameters):
  """Fetch a URL while authenticated as the service account.

  Args:
    method: The HTTP request method. E.g. 'GET', 'POST', 'PUT'.
    body: The request body as a Python object. It will be JSON-encoded.
    parameters: Parameters to be encoded in the URL query string.

  Returns:
    The reponse body.

  Raises:
    httplib.HTTPException: The request or response is malformed, or there is a
        network or server error, or the HTTP status code is not 2xx.
  """
  if parameters:
    # URL-encode the parameters.
    for key, value in parameters.iteritems():
      if value is None:
        del parameters[key]
      if isinstance(value, bool):
        parameters[key] = str(value).lower()
    url += '?' + urllib.urlencode(sorted(parameters.iteritems()), doseq=True)

  kwargs = {'method': method}
  if body:
    # JSON-encode the body.
    kwargs['body'] = json.dumps(body)
    kwargs['headers'] = {'Content-Type': 'application/json'}

  try:
    return _RequestAndProcessHttpErrors(url, **kwargs)
  except httplib.HTTPException:
    # Retry once.
    return _RequestAndProcessHttpErrors(url, **kwargs)


def _RequestAndProcessHttpErrors(*args, **kwargs):
  """Requests a URL, converting HTTP errors to Python exceptions."""
  http = utils.ServiceAccountHttp(timeout=10)
  response, content = http.request(*args, **kwargs)
  if not response['status'].startswith('2'):
    raise httplib.HTTPException(
        'HTTP status code %s: %s' % (response['status'], content))

  return content
