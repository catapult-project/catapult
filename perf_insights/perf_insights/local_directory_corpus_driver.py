# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights import corpus_driver
from perf_insights import local_file_trace_handle
from perf_insights import trace_run_info


def _GetFilesIn(basedir):
  data_files = []
  for dirpath, dirnames, filenames in os.walk(basedir, followlinks=True):
    new_dirnames = [d for d in dirnames if not d.startswith('.')]
    del dirnames[:]
    dirnames += new_dirnames
    for f in filenames:
      if f.startswith('.'):
        continue
      if f == 'README.md':
        continue
      full_f = os.path.join(dirpath, f)
      rel_f = os.path.relpath(full_f, basedir)
      data_files.append(rel_f)

  data_files.sort()
  return data_files


def _GetMetadataForFilename(base_directory, filename):
  # Tags.
  relpath = os.path.relpath(filename, base_directory)
  sub_dir = os.path.dirname(relpath)
  if len(sub_dir) == 0:
    tags = []
  else:
    tags = sub_dir.split(os.sep)

  metadata = {'tags': tags}

  # TODO(nduca): Add modification time to metadata.
  return metadata


class LocalDirectoryCorpusDriver(corpus_driver.CorpusDriver):
  def __init__(self, directory):
    self.directory = directory

  def GetTraceHandlesMatchingQuery(self, query):
    trace_handles = []

    files = _GetFilesIn(self.directory)
    for rel_filename in files:
      filename = os.path.join(self.directory, rel_filename)
      metadata = _GetMetadataForFilename(self.directory, filename)
      if not query.IsMetadataInteresting(metadata):
        continue

      run_info = trace_run_info.TraceRunInfo(
          url="file://%s" % filename,
          display_name=rel_filename)

      th = local_file_trace_handle.LocalFileTraceHandle(run_info, metadata,
                                                        filename)
      trace_handles.append(th)

    return trace_handles

