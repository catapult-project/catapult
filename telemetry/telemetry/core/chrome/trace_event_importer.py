# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from telemetry.core.chrome import timeline_model

def Import(data):
  trace = json.loads(data) # pylint: disable=W0612
  model = timeline_model.TimelineModel()

  # TODO(nduca): Actually import things.

  return model
