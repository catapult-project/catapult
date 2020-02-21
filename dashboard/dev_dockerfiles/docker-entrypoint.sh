#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

init_catapult() {
  # The current catapult deploy process & unit testing will generate
  # files in the directory. To prevent making any changes to the mounted
  # directory, we can just make a copy instead.
  if [[ -e /image/workspace ]]; then
    cp -r /image/workspace /workspace
    # TODO(dberris): This is a hack, which really shouldn't be required if we
    # remove the requirement that the deployment script be running in a git
    # repository.
    mkdir -p /workspace/.git/hooks
    cd /workspace/dashboard/dashboard
    make clean && make
    cd /workspace # All scripts in catapult assuming you in the repository
  fi
}

set_user_email() {
  # We only need to set the user email when both /image/workspace exist and
  # gcloud account configured. Because in other cases we don't neet to deploy
  # the service (gcloud not authed or without code)
  email=$(gcloud config get-value account 2>/dev/null)
  if [[ -e /image/workspace ]] && ! [[ -z "${email}" ]]; then
    git config --add user.email "${email}"
  fi
}

init_catapult
set_user_email
exec "$@"