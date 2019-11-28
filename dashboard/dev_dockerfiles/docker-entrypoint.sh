#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

if [[ -e /image/catapult ]]; then
  (cp -r /image/catapult / && \
  pushd /catapult/dashboard/dashboard &> /dev/null && \
  make clean && make
  popd &> /dev/null && \
  git config --add user.email ${GIT_COMMITTER_EMAIL}) || exit 1
fi

exec "$@"