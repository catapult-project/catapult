# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Helper methods for dealing with a SQLite database with pandas.
"""
import pandas.io.sql  # pylint: disable=import-error


def _InsertOrReplaceStatement(name, keys):
  columns = ','.join(keys)
  values = ','.join('?' for _ in keys)
  return 'INSERT OR REPLACE INTO %s(%s) VALUES (%s)' % (name, columns, values)


def InsertOrReplaceRecords(frame, name, conn):
  """Insert or replace records from a DataFrame into a SQLite database.

  Assumes that index columns of the frame have names, and those are used as to
  set the PRIMARY KEY of the table when creating anew. If the table already
  exists, any new records with a matching PRIMARY KEY will replace existing
  records.

  Args:
    frame: DataFrame with records to write.
    name: Name of SQL table.
    conn: A sqlite connection object.
  """
  db = pandas.io.sql.SQLiteDatabase(conn)
  if db.has_table(name):
    table = pandas.io.sql.SQLiteTable(
        name, db, frame=frame, index=True, if_exists='append')
    keys, data = table.insert_data()
    insert_statement = _InsertOrReplaceStatement(name, keys)
    with db.run_transaction() as c:
      c.executemany(insert_statement, zip(*data))
  else:
    table = pandas.io.sql.SQLiteTable(
        name, db, frame=frame, index=True, keys=frame.index.names,
        if_exists='fail')
    table.create()
    table.insert()
