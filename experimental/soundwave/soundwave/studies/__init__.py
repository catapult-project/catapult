#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from soundwave.studies import v8_study


_STUDIES = {'v8': v8_study}

NAMES = sorted(_STUDIES)


def IterTestPaths(api, study):
  return _STUDIES[study].IterTestPaths(api)
