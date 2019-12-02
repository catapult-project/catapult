#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

init_catapult() {
  # The current catapult deploy process & unit testing will generate
  # files in the directory. To prevent making any changes to the mounted
  # directory, we can just make a copy instead.
  if [[ -e /image/catapult ]]; then
    cp -r /image/catapult /
    cd /catapult/dashboard/dashboard
    make clean && make
    cd /catapult # All scripts in catapult assuming you in the repository
  fi
}

set_user_email() {
  # We only need to set the user email when both /image/catapult exist and
  # gcloud account configured. Because in other cases we don't neet to deploy
  # the service (gcloud not authed or without code)
  email=$(gcloud config get-value account 2>/dev/null)
  if [[ -e /image/catapult ]] && ! [[ -z "${email}" ]]; then
    git config --add user.email "${email}"
  fi
}

init_catapult
set_user_email
exec "$@"