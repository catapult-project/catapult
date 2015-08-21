# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import imp

def FindModule(name):
  """Gets the path of the named module.

  This is useful for cases where we want to use subprocess.call on a module we
  have imported, and safer than using __file__ since that can point to .pyc
  files.

  Args:
    name: the string name of a module (e.g. 'dev_appserver')
  Returns:
    The path to the module.
  """
  return imp.find_module(name)[1]
