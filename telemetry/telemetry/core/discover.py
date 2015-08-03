# Copyright 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch
import inspect
import os
import re

from telemetry.internal.util import classes as classes_module


def DiscoverModules(start_dir, top_level_dir, pattern='*'):
  """Discover all modules in |start_dir| which match |pattern|.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    pattern: Unix shell-style pattern for filtering the filenames to import.

  Returns:
    list of modules.
  """
  # start_dir and top_level_dir must be consistent with each other.
  start_dir = os.path.realpath(start_dir)
  top_level_dir = os.path.realpath(top_level_dir)

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

def DiscoverClasses(start_dir, top_level_dir, base_class, pattern='*',
                    one_class_per_module=False, directly_constructable=False):
  """Discover all classes in |start_dir| which subclass |base_class|.

  Base classes that contain subclasses are ignored by default.

  Args:
    start_dir: The directory to recursively search.
    top_level_dir: The top level of the package, for importing.
    base_class: The base class to search for.
    pattern: Unix shell-style pattern for filtering the filenames to import.
    one_class_per_module: If True, will only include the first class found in
                each module.
    directly_constructable: If True, will only return classes that can be
        constructed without arguments

  Returns: A list of classes.
  """
  modules = DiscoverModules(start_dir, top_level_dir, pattern)
  classes = []
  for module in modules:
    classes.extend(DiscoverClassesInModule(
        module, base_class, one_class_per_module, directly_constructable))
  return classes

def DiscoverClassesInModule(module, base_class, one_class_per_module=False,
                            directly_constructable=False):
  """Discover all classes in |module| which subclass |base_class|.

  Base classes that contain subclasses are ignored by default.

  Args:
    module: The module to search.
    base_class: The base class to search for.
    one_class_per_module: If True, will only include the first class found in
                each module.

  Returns: A list of classes.
  """
  classes = []
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

    if (not directly_constructable or
        classes_module.IsDirectlyConstructable(obj)):
      classes.append(obj)
      if one_class_per_module:
        return classes
  return classes


_counter = [0]
def _GetUniqueModuleName():
  _counter[0] += 1
  return "module_" + str(_counter[0])
