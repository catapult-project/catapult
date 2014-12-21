# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from trace_viewer import trace_viewer_project


FILE_GROUPS = ["tracing_css_files",
               "tracing_js_html_files",
               "tracing_img_files"]

def GetFileGroupFromFileName(filename):
   extension = os.path.splitext(filename)[1]
   return {
     '.css': 'tracing_css_files',
     '.html': 'tracing_js_html_files',
     '.js': 'tracing_js_html_files',
     '.png': 'tracing_img_files'
   }[extension]

def CheckListedFilesSorted(src_file, group_name, listed_files):
  sorted_files = sorted(listed_files)
  if sorted_files != listed_files:
    mismatch = ''
    for i in range(len(listed_files)):
      if listed_files[i] != sorted_files[i]:
        mismatch = listed_files[i]
        break
    what_is = '  ' + '\n  '.join(listed_files)
    what_should_be = '  ' + '\n  '.join(sorted_files)
    return '''In group {0} from file {1}, filenames aren't sorted.

First mismatch:
  {2}

Current listing:
{3}

Correct listing:
{4}\n\n'''.format(group_name, src_file, mismatch, what_is, what_should_be)
  else:
    return ''

def GetKnownFiles():
  p = trace_viewer_project.TraceViewerProject()
  m = p.loader.LoadModule(module_name='extras.about_tracing.about_tracing')
  absolute_filenames = m.GetAllDependentFilenamesRecursive(
      include_raw_scripts=False)

  return list(set([os.path.relpath(f, p.trace_viewer_path)
                   for f in absolute_filenames]))

def CheckCommon(file_name, listed_files):
  project = trace_viewer_project.TraceViewerProject()
  build_dir = os.path.join(project.src_path, 'build')

  known_files = GetKnownFiles()
  u = set(listed_files).union(set(known_files))
  i = set(listed_files).intersection(set(known_files))
  diff = list(u - i)

  if len(diff) == 0:
    return ''

  error = 'Entries in ' + file_name + ' do not match files on disk:\n'
  in_file_only = list(set(listed_files) - set(known_files))
  in_known_only = list(set(known_files) - set(listed_files))

  if len(in_file_only) > 0:
    error += '  In file only:\n    ' + '\n    '.join(sorted(in_file_only))
  if len(in_known_only) > 0:
    if len(in_file_only) > 0:
      error += '\n\n'
    error += '  On disk only:\n    ' + '\n    '.join(sorted(in_known_only))

  return error
