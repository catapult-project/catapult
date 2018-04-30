/*
Copyright 2018 The Chromium Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
*/

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
