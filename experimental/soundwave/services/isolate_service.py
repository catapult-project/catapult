#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import os
import zlib

from services import request


class Api(object):
  SERVICE_URL = 'https://chrome-isolated.appspot.com/_ah/api/isolateservice/v1'
  CACHE_DIR = os.path.normpath(os.path.join(
      os.path.dirname(__file__), '..', '_isolate_cache'))

  def __init__(self, credentials):
    self._credentials = credentials
    if not os.path.isdir(self.CACHE_DIR):
      os.makedirs(self.CACHE_DIR)

  def Request(self, endpoint, **kwargs):
    """Send a request to some isolate service endpoint."""
    kwargs.setdefault('credentials', self._credentials)
    return json.loads(request.Request(self.SERVICE_URL + endpoint, **kwargs))

  def Retrieve(self, digest):
    """Retrieve the content stored at some isolate digest."""
    return zlib.decompress(self.RetrieveCompressed(digest))

  def RetrieveFile(self, digest, filename):
    """Retrieve a particular filename from an isolate container."""
    container = json.loads(self.Retrieve(digest))
    return self.Retrieve(container['files'][filename]['h'])

  def RetrieveCompressed(self, digest):
    """Retrieve the compressed content stored at some isolate digest.

    Responses are cached locally to speed up retrieving content multiple times
    for the same digest.
    """
    cache_file = os.path.join(self.CACHE_DIR, digest)
    if os.path.exists(cache_file):
      with open(cache_file, 'rb') as f:
        return f.read()
    else:
      content = self._RetrieveCompressed(digest)
      with open(cache_file, 'wb') as f:
        f.write(content)
      return content

  def _RetrieveCompressed(self, digest):
    """Retrieve the compressed content stored at some isolate digest."""
    data = self.Request(
        '/retrieve', method='POST', content_type='json',
        data={'namespace': {'namespace': 'default-gzip'}, 'digest': digest})

    if 'url' in data:
      return request.Request(data['url'])
    if 'content' in data:
      return base64.b64decode(data['content'])
    else:
      raise NotImplementedError(
          'Isolate %s in unknown format %s' % (digest, json.dumps(data)))
