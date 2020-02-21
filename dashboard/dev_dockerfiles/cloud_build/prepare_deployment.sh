#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

cd /workspace/dashboard

# Run the deploy script in dry-run mode, using the shared volume in the cloud
# build environment, and copying the files instead of symlinking.
./bin/deploy --dry_run --target_dir /workspace/deploy-dashboard --copy_files
