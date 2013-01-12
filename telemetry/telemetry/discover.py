# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import inspect
import logging
import os
import traceback

def Discover(start_dir, suffix, clazz, import_error_should_raise=False):
  """Discover all classes in |start_dir| which subclass |clazz|.

  Args:
    start_dir: The directory to recursively search.
    suffix: file name suffix for files to import, without the '.py' ending.
    clazz: The base class to search for.
    import_error_should_raise: If false, then import errors are logged but do
      not stop discovery.

  Returns:
    dict of {module_name: class}.
  """
  top_level_dir = os.path.join(start_dir, '..')
  classes = {}
  for dirpath, _, filenames in os.walk(start_dir):
    for filename in filenames:
      if not filename.endswith(suffix + '.py'):
        continue
      name, _ = os.path.splitext(filename)
      relpath = os.path.relpath(dirpath, top_level_dir)
      fqn = relpath.replace('/', '.') + '.' + name
      try:
        module = __import__(fqn, fromlist=[True])
      except Exception:
        if import_error_should_raise:
          raise
        logging.error('While importing [%s]\n' % fqn)
        traceback.print_exc()
        continue
      for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj):
          if clazz in inspect.getmro(obj):
            name = module.__name__.split('.')[-1]
            classes[name] = obj
  return classes
