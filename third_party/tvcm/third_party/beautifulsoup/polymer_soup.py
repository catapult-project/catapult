# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import BeautifulSoup


class PolymerSoup(BeautifulSoup.BeautifulSoup):
  """Parser for HTML files containing Polymer tags."""
  NESTABLE_TAGS = BeautifulSoup.BeautifulSoup.NESTABLE_TAGS.copy()
  NESTABLE_TAGS['template'] = []
