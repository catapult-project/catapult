# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import random
import sys
import tempfile

from telemetry import value as value_module
from telemetry.util import cloud_storage
from telemetry.util import file_handle
import telemetry.web_components # pylint: disable=W0611
from trace_viewer.build import trace2html

class TraceValue(value_module.Value):
  def __init__(self, page, tracing_timeline_data, important=False,
               description=None):
    """A value that contains a TracingTimelineData object and knows how to
    output it.

    Adding TraceValues and outputting as JSON will produce a directory full of
    HTML files called trace_files. Outputting as chart JSON will also produce
    an index, files.html, linking to each of these files.
    """
    super(TraceValue, self).__init__(
        page, name='trace', units='', important=important,
        description=description)

    tf = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
    if page:
      title = page.display_name
    else:
      title = ''
    trace2html.WriteHTMLForTraceDataToFile(
        [tracing_timeline_data.EventData()], title, tf)
    tf.close()

    self._file_handle = file_handle.FromTempFile(tf)
    self._cloud_url = None

  def GetAssociatedFileHandle(self):
    return self._file_handle

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
    return 'TraceValue(%s, %s)' % (page_name, self.name)

  def GetBuildbotDataType(self, output_context):
    return None

  def GetBuildbotValue(self):
    return None

  def GetRepresentativeNumber(self):
    return None

  def GetRepresentativeString(self):
    return None

  @staticmethod
  def GetJSONTypeName():
    return 'trace'

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    # TODO(eakuefner): Implement a MultiTraceValue: a Polymer-based,
    # componentized, MultiTraceViwer-backed representation of more than one
    # trace.
    assert len(values) > 0
    return values[0]

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    return None

  def AsDict(self):
    d = super(TraceValue, self).AsDict()
    d['file_id'] = self._file_handle.id
    return d

  def UploadToCloud(self, bucket):
    try:
      remote_path = ('trace-file-id_%s-%s-%d%s' % (
          self._file_handle.id,
          datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
          random.randint(1, 100000),
          self._file_handle.extension))
      self._cloud_url = cloud_storage.Insert(
          bucket, remote_path,
          self._file_handle.GetAbsPath())
      sys.stderr.write(
          'View generated trace files online at %s for page %s\n' %
          (self._cloud_url, self.page.url if self.page else 'unknown'))
    except cloud_storage.PermissionError as e:
      logging.error('Cannot upload trace files to cloud storage due to '
                    ' permission error: %s' % e.message)
