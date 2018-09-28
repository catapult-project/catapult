#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import zlib

from services import request


class Api(object):
  SERVICE_URL = 'https://chrome-isolated.appspot.com/_ah/api/isolateservice/v1'

  def __init__(self, credentials):
    self._credentials = credentials

  def Request(self, endpoint, **kwargs):
    """Send a request to some insolate service endpoint."""
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
