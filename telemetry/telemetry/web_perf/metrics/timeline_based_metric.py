# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class TimelineBasedMetric(object):
  def __init__(self):
    """Computes metrics from a telemetry.core.timeline Model and a range

    """
    super(TimelineBasedMetric, self).__init__()

  def AddResults(self, model, renderer_thread, interaction_records, results):
    """Computes and adds metrics for the interaction_records' time ranges.

    The override of this method should compute results on the data **only**
    within the interaction_records' start and end time ranges.

    model is an instance of telemetry.core.timeline.model.TimelineModel.
    interaction_records is a list of instances of TimelineInteractionRecord.
    results is an instance of page.PageTestResults.

    """
    raise NotImplementedError()
