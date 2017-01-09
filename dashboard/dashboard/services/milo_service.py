# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An interface to the milo service, which provides buildbot information.

The protocol buffer defining the API is located here:
https://github.com/luci/luci-go/blob/master/milo/api/proto/buildbot.proto

The API basically returns the same thing as the buildbot JSON API. We use the
milo API instead of raw buildbot json because this is the method supported by
Chrome infra team; the data is available longer and pinging the API does not
DOS buildbot pages.
"""

import base64
import json

from google.appengine.api import urlfetch

_BUILDBOT_JSON_URL = (
    'https://luci-milo.appspot.com/prpc/milo.Buildbot/'
    'GetBuildbotBuildJSON')


def GetBuildbotBuildInfo(master, builder, build_num):
  body = json.dumps({
      'master': master,
      'builder': builder,
      'build_num': int(build_num)
  })
  headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
  }
  try:
    response = urlfetch.fetch(
        url=_BUILDBOT_JSON_URL,
        method=urlfetch.POST,
        payload=body,
        headers=headers)
  except urlfetch.Error:
    return None
  if response.status_code != 200:
    return None

  # Unwrap the gRPC message
  resp = json.loads(response.content[5:])  # Remove the jsonp header.
  # Decompress and unmarshal the json message.
  data = base64.b64decode(resp['data'])
  if not data:
    return None
  result = json.loads(data)
  # Convert properties and steps lists to dicts
  properties = {p[0] : p[1] for p in result['properties']}
  result['properties'] = properties
  steps = {step['name'] : step for step in result['steps']}
  result['steps'] = steps
  result['masterName'] = master
  return result
