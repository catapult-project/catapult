# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper methods for working with histograms and diagnostics."""

from tracing.value.diagnostics import reserved_infos


def GetTIRLabelFromHistogram(hist):
  tags = hist.diagnostics.get(reserved_infos.STORY_TAGS.name) or []

  tags_to_use = [t.split(':') for t in tags if ':' in t]

  return '_'.join(v for _, v in sorted(tags_to_use))
