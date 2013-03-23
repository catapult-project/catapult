# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import fnmatch
import inspect
import logging
import os
import re
import traceback


def DiscoverModules(start_dir, top_level_dir, pattern='*',
                    import_error_should_raise=False):
  """Discover all modules in |start_dir| which match |pattern|.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    pattern: Unix shell-style pattern for filtering the filenames to import.
    import_error_should_raise: If false, then import errors are logged but do
      not stop discovery.

  Returns:
    list of modules.
  """
  modules = []
  for dir_path, _, filenames in os.walk(start_dir):
    for filename in filenames:
      # Filter out unwanted filenames.
      if filename.startswith('.') or filename.startswith('_'):
        continue
      if os.path.splitext(filename)[1] != '.py':
        continue
      if not fnmatch.fnmatch(filename, pattern):
        continue

      # Find the module.
      module_rel_path = os.path.relpath(os.path.join(dir_path, filename),
                                        top_level_dir)
      module_name = re.sub(r'[/\\]', '.', os.path.splitext(module_rel_path)[0])

      # Import the module.
      try:
        module = __import__(module_name, fromlist=[True])
      except ImportError:
        if import_error_should_raise:
          raise
        logging.error('While importing [%s]\n' % module_name)
        traceback.print_exc()
        continue

      modules.append(module)
  return modules


def DiscoverClasses(start_dir, top_level_dir, base_class, pattern='*',
                    import_error_should_raise=False):
  """Discover all classes in |start_dir| which subclass |base_class|.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    base_class: The base class to search for.
    pattern: Unix shell-style pattern for filtering the filenames to import.
    import_error_should_raise: If false, then import errors are logged but do
      not stop discovery.

  Returns:
    dict of {module_name: class}.
  """
  modules = DiscoverModules(start_dir, top_level_dir, pattern,
                            import_error_should_raise)
  classes = {}
  for module in modules:
    for name, obj in inspect.getmembers(module):
      if inspect.isclass(obj) and base_class in inspect.getmro(obj):
        name = module.__name__.split('.')[-1]
        classes[name] = obj
  return classes
