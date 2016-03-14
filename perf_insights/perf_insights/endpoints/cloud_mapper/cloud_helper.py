# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import cloudstorage as gcs


class EnvVarModifier(object):
  def __init__(self, **kwargs):
    self._vars = {}
    self._kwargs = kwargs

  def __enter__(self):
    for k, v in self._kwargs.iteritems():
      self._vars[k] = os.environ.get(k)
      os.environ[k] = v
    return self

  def __exit__(self, *_):
    for k, v in self._vars.iteritems():
      os.environ[k] = v


default_retry_params = gcs.RetryParams(initial_delay=0.2,
                                       max_delay=5.0,
                                       backoff_factor=2,
                                       max_retry_period=15)
gcs.set_default_retry_params(default_retry_params)


def _remove_gcs_prefix(full_url):
  return full_url.split('gs:/')[1]


def WriteGCS(fullurl, data):
  with EnvVarModifier(SERVER_SOFTWARE='') as _:
    gcs_file = gcs.open(_remove_gcs_prefix(fullurl),
                        'w',
                        content_type='text/plain',
                        options={},
                        retry_params=default_retry_params)
    gcs_file.write(data)
    gcs_file.close()


def ReadGCS(fullurl):
  with EnvVarModifier(SERVER_SOFTWARE='') as _:
    gcs_file = gcs.open(_remove_gcs_prefix(fullurl),
                        'r',
                        retry_params=default_retry_params)

    contents = gcs_file.read()
    gcs_file.close()

    return contents


def ReadGCSToFile(fullurl, output_file):
  output_file.write(ReadGCS(fullurl))


def StatGCS(fullurl):
  with EnvVarModifier(SERVER_SOFTWARE='') as _:
    try:
      return gcs.stat(_remove_gcs_prefix(fullurl))
    except gcs.NotFoundError:
      return None
