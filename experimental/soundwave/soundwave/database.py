# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sqlite3


class Database(object):
  def __init__(self, filename, schema):
    self._conn = sqlite3.connect(filename)
    with self._conn:
      with open(schema) as f:
        self._conn.executescript(f.read())
    self._put = {}

  def __enter__(self):
    self._conn.__enter__()
    return self

  def __exit__(self, *args, **kwargs):
    self._conn.__exit__(*args, **kwargs)

  def Put(self, item):
    table = type(item)
    if table.name not in self._put:
      self._put[table.name] = 'INSERT OR IGNORE INTO %s VALUES (%s)' % (
          table.name, ','.join('?' * len(table.columns)))
    self._conn.execute(self._put[table.name], item)
