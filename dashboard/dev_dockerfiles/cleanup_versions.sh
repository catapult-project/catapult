#!/bin/bash -x -e
# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

for SERVICE in "$@"; do
  gcloud app versions list \
    --format="table[no-heading](VERSION.ID)" \
    --filter="SERVICE=${SERVICE} AND
              TRAFFIC_SPLIT=0 AND
              LAST_DEPLOYED.date()<$(date -I --date='-60 day')" \
  | xargs --no-run-if-empty gcloud app versions delete -s ${SERVICE}
done