# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class FunctionHandle(object):
  def __init__(self, filename=None, function_name=None):
    if filename is None and function_name is None:
      raise Exception('Must provide filename or mapperName')
    self.filename = filename
    self.function_name = function_name

  def __repr__(self):
    if self.filename:
      return 'FunctionHandle(filename="%s")' % self.filename
    return 'FunctionHandle(function_name="%s")' % self.function_name

  def AsDict(self):
    if self.filename is not None:
      return {'filename': self.filename}
    return {'function_name': self.function_name}
