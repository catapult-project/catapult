# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import third_party.cloudstorage as gcs

default_retry_params = gcs.RetryParams(initial_delay=0.2,
                                       max_delay=5.0,
                                       backoff_factor=2,
                                       max_retry_period=15)
gcs.set_default_retry_params(default_retry_params)


def _remove_gcs_prefix(full_url):
  return full_url.split('gs:/')[1]


def WriteGCS(fullurl, data):
  gcs_file = gcs.open(_remove_gcs_prefix(fullurl),
                      'w',
                      content_type='text/plain',
                      options={},
                      retry_params=default_retry_params)
  gcs_file.write(data)
  gcs_file.close()


def ReadGCS(fullurl):
  gcs_file = gcs.open(_remove_gcs_prefix(fullurl),
                      'r',
                      retry_params=default_retry_params)

  contents = gcs_file.read()
  gcs_file.close()

  return contents


def ReadGCSToFile(fullurl, output_file):
  output_file.write(ReadGCS(fullurl))


def StatGCS(fullurl):
  try:
    return gcs.stat(_remove_gcs_prefix(fullurl))
  except gcs.NotFoundError:
    return None
