# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import httplib
import json
import socket
import urllib2

from telemetry.core import exceptions


class DevToolsClientConnectionError(exceptions.Error):
  pass


class DevToolsClientUrlError(DevToolsClientConnectionError):
  pass


class DevToolsHttp(object):
  """A helper class to send and parse DevTools HTTP requests."""

  def __init__(self, devtools_port):
    self._devtools_port = devtools_port

  def Request(self, path, timeout=30):
    """
    Args:
      path: The DevTools URL path, without the /json/ prefix.
      timeout: Timeout defaults to 30 seconds.

    Raises:
      DevToolsClientConnectionError: If the connection fails.
    """
    url = 'http://127.0.0.1:%i/json' % self._devtools_port
    if path:
      url += '/' + path
    try:
      proxy_handler = urllib2.ProxyHandler({})  # Bypass any system proxy.
      opener = urllib2.build_opener(proxy_handler)
      with contextlib.closing(opener.open(url, timeout=timeout)) as req:
        return req.read()
    except urllib2.URLError as e:
      raise DevToolsClientUrlError(e)
    except (socket.error, httplib.BadStatusLine) as e:
      raise DevToolsClientConnectionError(e)

  def RequestJson(self, path, timeout=30):
    """Sends a request and parse the response as JSON.

    Args:
      path: The DevTools URL path, without the /json/ prefix.
      timeout: Timeout defaults to 30 seconds.

    Raises:
      DevToolsClientConnectionError: If the connection fails.
      ValueError: If the response is not a valid JSON.
    """
    return json.loads(self.Request(path, timeout))
