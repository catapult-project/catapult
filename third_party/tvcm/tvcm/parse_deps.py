# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
The core of this script is the calc_load_sequence function. This function
walks over the provided javascript files and figures out their dependencies
by reading the base.require statements in each file. This allows us to, for
example, have a trio of modules, foo, bar and baz, where foo.js contains:

    base.require('bar');

and bar.js contains:

    base.require('baz');

If these three modules are in the current directory, then:

    calc_load_sequence(['foo'], '.')

Will return the correct sequence in which to load these modules based on these
dependencies, which is: [Module('baz'), Module('bar'), Module('foo')].
"""

import os

from tvcm import module
from tvcm import resource_loader


def calc_load_sequence(filenames, search_paths, data_paths):
  """Given a list of starting javascript files, figure out all the Module
  objects that need to be loaded to satisfy their dependencies.

  The javascript files should specify their dependencies in a format that is
  textually equivalent to base/__init__.js' require syntax, namely:

      base.require(module1);
      base.require(module2);
      base.requireStylesheet(stylesheet);

  Args:
    filenames: A list of starting file paths for trace viewer modules.
    search_paths: A list of top-level directories in which modules can be found.
        Module paths are relative to these directories.
    data_paths: A list of top-level directories in which raw scripts and other
        directly-referenced resources can be found.

  Returns:
    A list of Module objects in the order that they should be loaded.
  """
  if os.path.join('base', '__init__.js') not in filenames:
    filenames = list(filenames)
    filenames.insert(0, os.path.join('base', '__init__.js'))
  return calc_load_sequence_internal(filenames, search_paths, data_paths)


def calc_load_sequence_internal(filenames, search_paths, data_paths):
  """Helper function for calc_load_sequence.

  Args:
    filenames: A list of starting file paths for trace viewer modules.
    search_paths: A list of top-level directories to search in.

  Returns:
    A list of Module objects in the list that they should be loaded.
  """
  loader = resource_loader.ResourceLoader(search_paths, data_paths)
  initial_module_name_indices = {}
  for filename in filenames:
    m = loader.load_module(module_filename=filename)
    if m.name not in initial_module_name_indices:
      initial_module_name_indices[m.name] = len(initial_module_name_indices)

  # Find the root modules: ones that have no dependencies. While doing that,
  # sort the dependent module list so that the computed load order is stable.
  module_ref_counts = {}
  for m in loader.loaded_scripts.values():
    m.dependent_modules.sort(lambda x, y: cmp(x.name, y.name))
    module_ref_counts[m.name] = 0

  # Count the number of references to each module.
  def inc_ref_count(name):
    module_ref_counts[name] = module_ref_counts[name] + 1
  for m in loader.loaded_scripts.values():
    for dependent_module in m.dependent_modules:
      inc_ref_count(dependent_module.name)

  # Root modules are modules with nothing depending on them.
  root_modules = [loader.loaded_scripts[name]
                  for name, ref_count in module_ref_counts.items()
                  if ref_count == 0]

  # Sort root_modules by the order they were originally requested,
  # then sort everything else by name.
  def compare_root_module(x, y):
    n = len(initial_module_name_indices)
    iX = initial_module_name_indices.get(x.name, n)
    iY = initial_module_name_indices.get(y.name, n)
    if cmp(iX, iY) != 0:
      return cmp(iX, iY)
    return cmp(x.name, y.name)
  root_modules.sort(compare_root_module)

  already_loaded_set = set()
  load_sequence = []
  for m in root_modules:
    m.compute_load_sequence_recursive(load_sequence, already_loaded_set)
  return load_sequence
