# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class MapFunctionHandle(object):
  def __init__(self, filename=None, map_function_name=None):
    if filename is None and map_function_name is None:
      raise Exception('Must provide filename or mapperName')
    self.filename = filename
    self.map_function_name = map_function_name

  def __repr__(self):
    if self.filename:
      return 'MapFunctionHandle(filename="%s")' % self.filename
    return 'MapFunctionHandle(map_function_name="%s")' % self.map_function_name

  def AsDict(self):
    if self.filename is not None:
      return {'mapFunctionFileName': self.filename}
    return {'mapFunctionName': self.map_function_name}
