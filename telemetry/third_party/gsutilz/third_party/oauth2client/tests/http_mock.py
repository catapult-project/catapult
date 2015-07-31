# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Copy of googleapiclient.http's mock functionality."""

import json

import httplib2

# TODO(craigcitro): Find a cleaner way to share this code with googleapiclient.


class HttpMock(object):
  """Mock of httplib2.Http"""

  def __init__(self, filename=None, headers=None):
    """
    Args:
      filename: string, absolute filename to read response from
      headers: dict, header to return with response
    """
    if headers is None:
      headers = {'status': '200 OK'}
    if filename:
      f = file(filename, 'r')
      self.data = f.read()
      f.close()
    else:
      self.data = None
    self.response_headers = headers
    self.headers = None
    self.uri = None
    self.method = None
    self.body = None
    self.headers = None


  def request(self, uri,
              method='GET',
              body=None,
              headers=None,
              redirections=1,
              connection_type=None):
    self.uri = uri
    self.method = method
    self.body = body
    self.headers = headers
    return httplib2.Response(self.response_headers), self.data


class HttpMockSequence(object):
  """Mock of httplib2.Http

  Mocks a sequence of calls to request returning different responses for each
  call. Create an instance initialized with the desired response headers
  and content and then use as if an httplib2.Http instance.

    http = HttpMockSequence([
      ({'status': '401'}, b''),
      ({'status': '200'}, b'{"access_token":"1/3w","expires_in":3600}'),
      ({'status': '200'}, 'echo_request_headers'),
      ])
    resp, content = http.request("http://examples.com")

  There are special values you can pass in for content to trigger
  behavours that are helpful in testing.

  'echo_request_headers' means return the request headers in the response body
  'echo_request_headers_as_json' means return the request headers in
     the response body
  'echo_request_body' means return the request body in the response body
  'echo_request_uri' means return the request uri in the response body
  """

  def __init__(self, iterable):
    """
    Args:
      iterable: iterable, a sequence of pairs of (headers, body)
    """
    self._iterable = iterable
    self.follow_redirects = True
    self.requests = []

  def request(self, uri,
              method='GET',
              body=None,
              headers=None,
              redirections=1,
              connection_type=None):
    resp, content = self._iterable.pop(0)
    self.requests.append({'uri': uri, 'body': body, 'headers': headers})
    # Read any underlying stream before sending the request.
    body_stream_content = body.read() if getattr(body, 'read', None) else None
    if content == 'echo_request_headers':
      content = headers
    elif content == 'echo_request_headers_as_json':
      content = json.dumps(headers)
    elif content == 'echo_request_body':
      content = body if body_stream_content is None else body_stream_content
    elif content == 'echo_request_uri':
      content = uri
    elif not isinstance(content, bytes):
      raise TypeError('http content should be bytes: %r' % (content,))
    return httplib2.Response(resp), content
