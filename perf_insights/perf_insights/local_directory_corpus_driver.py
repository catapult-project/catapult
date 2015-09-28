# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from perf_insights import corpus_driver
from perf_insights import local_file_trace_handle
from perf_insights.value import run_info as run_info_module


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

def _GetTagsForRelPath(relpath):
  # Tags.
  sub_dir = os.path.dirname(relpath)
  if len(sub_dir) == 0:
    return []
  parts = sub_dir.split(os.sep)
  return [p for p in parts if len(p) > 0]

def _GetMetadataForFilename(base_directory, filename):
  relpath = os.path.relpath(filename, base_directory)
  tags = _GetTagsForRelPath(relpath)

  metadata = {'tags': tags}

  # TODO(nduca): Add modification time to metadata.
  return metadata

def _DefaultUrlResover(abspath):
  return 'file:///%s' % abspath

class LocalDirectoryCorpusDriver(corpus_driver.CorpusDriver):
  def __init__(self, directory, url_resolver = None):
    self.directory = directory
    if url_resolver == None:
      self.url_resolver = _DefaultUrlResover
    else:
      self.url_resolver = url_resolver

  def GetTraceHandlesMatchingQuery(self, query):
    trace_handles = []

    files = _GetFilesIn(self.directory)
    for rel_filename in files:
      filename = os.path.join(self.directory, rel_filename)
      metadata = _GetMetadataForFilename(self.directory, filename)

      if not query.Eval(metadata, len(trace_handles)):
        continue

      # Make URL relative to server root.
      url = self.url_resolver(filename)
      if url is None:
        url = _DefaultUrlResover(filename)
      run_info = run_info_module.RunInfo(
          url=url,
          display_name=rel_filename,
          metadata=metadata)

      th = local_file_trace_handle.LocalFileTraceHandle(run_info, filename)
      trace_handles.append(th)

    return trace_handles

