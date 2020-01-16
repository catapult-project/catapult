#!/bin/bash
# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
set -e

cd /workspace/dashboard/dashboard

make

cd /workspace/dashboard

# TODO(dberris): This is a hack, which really shouldn't be required if we remove
# the requirement that the deployment script be running in a git repository.
mkdir -p /workspace/.git/hooks

# TODO(fancl): Add dev server tests
./bin/run_py_tests -t -v
