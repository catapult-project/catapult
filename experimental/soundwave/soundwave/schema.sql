/*
Copyright 2018 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
*/

CREATE TABLE IF NOT EXISTS alerts (
  key TEXT PRIMARY KEY,
  timestamp INTEGER NOT NULL,
  test_suite TEXT NOT NULL,
  measurement TEXT NOT NULL,
  bot TEXT NOT NULL,
  test_case TEXT NOT NULL,
  start_revision TEXT NOT NULL,
  end_revision TEXT NOT NULL,
  median_before_anomaly REAL NOT NULL,
  median_after_anomaly REAL NOT NULL,
  units TEXT,
  improvement BOOLEAN NOT NULL,
  bug_id INTEGER,
  status TEXT NOT NULL,
  bisect_status TEXT
);

CREATE TABLE IF NOT EXISTS bugs (
  id INTEGER PRIMARY KEY,
  summary TEXT NOT NULL,
  published INTEGER NOT NULL,
  updated INTEGER NOT NULL,
  state TEXT NOT NULL,
  status TEXT NOT NULL,
  author TEXT NOT NULL,
  owner TEXT,
  cc TEXT,
  components TEXT,
  labels TEXT
)
