#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Query build slave hardware info, and print it to stdout as csv."""

import cStringIO
import csv
import json
import mimetools
import sys
import urllib2


_MASTERS = [
    'chromium.perf',
    'tryserver.chromium.perf',
]


_KEYS = [
    'master', 'builder', 'hostname',
    'osfamily', 'os version', 'windows version',
    'product name', 'architecture', 'processor count', 'memory total',
    'git version',
    'android device 1', 'android device 2',
    'android device 3', 'android device 4',
    'android device 5', 'android device 6',
    'android device 7', 'android device 8',
]


def main():
  writer = csv.DictWriter(sys.stdout, _KEYS)
  writer.writeheader()

  for master_name in _MASTERS:
    master_data = json.load(urllib2.urlopen(
      'http://build.chromium.org/p/%s/json/slaves' % master_name))

    slaves = sorted(master_data.iteritems(), key=lambda x: x[1]['builders'])
    for slave_name, slave_data in slaves:
      for builder_name in slave_data['builders']:
        row = {
            'master': master_name,
            'builder': builder_name,
            'hostname': slave_name,
        }

        host_data = slave_data['host']
        if host_data:
          row.update(dict(mimetools.Message(cStringIO.StringIO(host_data))))

        if 'product name' not in row and slave_name.startswith('slave'):
          row['product name'] = 'Google Compute Engine'

        writer.writerow(row)


if __name__ == '__main__':
  main()
