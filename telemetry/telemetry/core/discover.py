# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch
import inspect
import os
import re

from telemetry import decorators
from telemetry.core import camel_case


@decorators.Cache
def DiscoverModules(start_dir, top_level_dir, pattern='*'):
  """Discover all modules in |start_dir| which match |pattern|.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    pattern: Unix shell-style pattern for filtering the filenames to import.

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
      module = __import__(module_name, fromlist=[True])

      modules.append(module)
  return modules


# TODO(dtu): Normalize all discoverable classes to have corresponding module
# and class names, then always index by class name.
@decorators.Cache
def DiscoverClasses(start_dir, top_level_dir, base_class, pattern='*',
                    index_by_class_name=False):
  """Discover all classes in |start_dir| which subclass |base_class|.

  Base classes that contain subclasses are ignored by default.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    base_class: The base class to search for.
    pattern: Unix shell-style pattern for filtering the filenames to import.
    index_by_class_name: If True, use class name converted to
        lowercase_with_underscores instead of module name in return dict keys.

  Returns:
    dict of {module_name: class} or {underscored_class_name: class}
  """
  modules = DiscoverModules(start_dir, top_level_dir, pattern)
  classes = {}
  for module in modules:
    new_classes = DiscoverClassesInModule(
        module, base_class, index_by_class_name)
    classes = dict(classes.items() + new_classes.items())
  return classes

@decorators.Cache
def DiscoverClassesInModule(module, base_class, index_by_class_name=False):
  """Discover all classes in |module| which subclass |base_class|.

  Base classes that contain subclasses are ignored by default.

  Args:
    module: The module to search.
    base_class: The base class to search for.
    index_by_class_name: If True, use class name converted to
        lowercase_with_underscores instead of module name in return dict keys.

  Returns:
    dict of {module_name: class} or {underscored_class_name: class}
  """
  classes = {}
  for _, obj in inspect.getmembers(module):
    # Ensure object is a class.
    if not inspect.isclass(obj):
      continue
    # Include only subclasses of base_class.
    if not issubclass(obj, base_class):
      continue
    # Exclude the base_class itself.
    if obj is base_class:
      continue
    # Exclude protected or private classes.
    if obj.__name__.startswith('_'):
      continue
    # Include only the module in which the class is defined.
    # If a class is imported by another module, exclude those duplicates.
    if obj.__module__ != module.__name__:
      continue

    if index_by_class_name:
      key_name = camel_case.ToUnderscore(obj.__name__)
    else:
      key_name = module.__name__.split('.')[-1]
    classes[key_name] = obj

  return classes


_counter = [0]
def _GetUniqueModuleName():
  _counter[0] += 1
  return "module_" + str(_counter[0])
