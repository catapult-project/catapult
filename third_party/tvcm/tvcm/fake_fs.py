# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys
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

  def __enter__(self):
    self.Bind()
    return self

  def __exit__(self, *args):
    self.Unbind()

  def Bind(self):
    assert not self._bound
    sys.modules['__builtin__'].open = self._FakeOpen
    os.path.exists = self._FakeExists
    self._bound = True

  def Unbind(self):
    assert self._bound
    sys.modules['__builtin__'].open = self._real_open
    os.path.exists = self._real_exists
    self._bound = False

  def AddFile(self, path, contents):
    assert path not in self._file_contents
    self._file_contents[path] = contents

  def _FakeOpen(self, path, mode=None):
    if mode == None:
      mode = 'r'
    if mode == 'r' or mode == 'rU':
      if path not in self._file_contents:
        return self._real_open(path, mode)
      return WithableStringIO(self._file_contents[path])

    raise NotImplementedError()

  def _FakeExists(self, path):
    if path in self._file_contents:
      return True
    return self._real_exists(path)
