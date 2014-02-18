# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
import collections
import StringIO

class WithableStringIO(StringIO.StringIO):
  def __enter__(self, *args):
    return self

  def __exit__(self, *args):
    pass

class FakeFS(object):
  def __init__(self, initial_filenames_and_contents=None):
    self._file_contents = {}
    if initial_filenames_and_contents:
      for k,v in initial_filenames_and_contents.iteritems():
        self._file_contents[k] = v

    self._bound = False
    self._real_open = sys.modules['__builtin__'].open
    self._real_exists = os.path.exists
    self._real_walk = os.walk
    self._real_listdir = os.listdir

  def __enter__(self):
    self.Bind()
    return self

  def __exit__(self, *args):
    self.Unbind()

  def Bind(self):
    assert not self._bound
    sys.modules['__builtin__'].open = self._FakeOpen
    os.path.exists = self._FakeExists
    os.walk = self._FakeWalk
    os.listdir = self._FakeListDir
    self._bound = True

  def Unbind(self):
    assert self._bound
    sys.modules['__builtin__'].open = self._real_open
    os.path.exists = self._real_exists
    os.walk = self._real_walk
    os.listdir = self._real_listdir
    self._bound = False

  def AddFile(self, path, contents):
    assert path not in self._file_contents
    self._file_contents[path] = contents

  def _FakeOpen(self, path, mode=None):
    if mode == None:
      mode = 'r'
    if mode == 'r' or mode == 'rU' or mode == 'rb':
      if path not in self._file_contents:
        return self._real_open(path, mode)
      return WithableStringIO(self._file_contents[path])

    raise NotImplementedError()

  def _FakeExists(self, path):
    if path in self._file_contents:
      return True
    return self._real_exists(path)

  def _FakeWalk(self, top):
    assert os.path.isabs(top)
    all_filenames = self._file_contents.keys()
    pending_prefixes = collections.deque()
    pending_prefixes.append(top)
    visited_prefixes = set()
    while len(pending_prefixes):
      prefix = pending_prefixes.popleft()
      if prefix in visited_prefixes:
        continue
      visited_prefixes.add(prefix)
      if prefix.endswith('/'):
        prefix_with_trailing_sep = prefix
      else:
        prefix_with_trailing_sep = prefix + '/'

      dirs = set()
      files = []
      for filename in all_filenames:
        if not filename.startswith(prefix_with_trailing_sep):
          continue
        relative_to_prefix = os.path.relpath(filename, prefix)

        dirpart = os.path.dirname(relative_to_prefix)
        if len(dirpart) == 0:
          files.append(relative_to_prefix)
          continue
        parts = dirpart.split('/')
        if len(parts) == 0:
          dirs.add(dirpart)
        else:
          if prefix.endswith('/'):
            pending = prefix + parts[0]
          else:
            pending = prefix + '/' + parts[0]
          dirs.add(parts[0])
          pending_prefixes.appendleft(pending)

      dirs = list(dirs)
      dirs.sort()
      yield prefix, dirs, files

  def _FakeListDir(self, dirname):
    raise NotImplementedError()
