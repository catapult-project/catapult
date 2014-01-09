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
from tvcm import resource_finder


def calc_load_sequence(filenames, search_paths):
  """Given a list of starting javascript files, figure out all the Module
  objects that need to be loaded to satisfy their dependencies.

  The javascript files should specify their dependencies in a format that is
  textually equivalent to base.js' require syntax, namely:

      base.require(module1);
      base.require(module2);
      base.requireStylesheet(stylesheet);

  Args:
    filenames: A list of starting file paths for trace viewer modules.
    search_paths: A list of top-level directories that dependencies can be
        searched for in. Module paths are relative to these directories.

  Returns:
    A list of Module objects in the order that they should be loaded.
  """
  if 'base.js' not in filenames:
    filenames = list(filenames)
    filenames.insert(0, 'base.js')
  return calc_load_sequence_internal(filenames, search_paths)


def calc_load_sequence_internal(filenames, search_paths):
  """Helper function for calc_load_sequence.

  Args:
    filenames: A list of starting file paths for trace viewer modules.
    search_paths: A list of top-level directories to search in.

  Returns:
    A list of Module objects in the list that they should be loaded.
  """
  all_resources = {}
  all_resources['scripts'] = {}
  finder = resource_finder.ResourceFinder(search_paths)
  initial_module_name_indices = {}
  for filename in filenames:
    resolved = finder.resolve(filename)
    if not resolved:
      raise Exception('Could not find %s in %s' % (
          filename, repr(finder.search_paths)))

    dirname = os.path.dirname(resolved.relative_path)
    modname  = os.path.splitext(os.path.basename(resolved.relative_path))[0]
    if len(dirname):
      name = dirname.replace(os.path.sep, '.') + '.' + modname
    else:
      name = modname

    if name in all_resources['scripts']:
      continue

    m = module.Module(name)
    initial_module_name_indices[m.name] = len(initial_module_name_indices)
    m.load_and_parse(resolved.absolute_path, decl_required=False)
    all_resources['scripts'][m.name] = m
    m.resolve(all_resources, finder)

  # Find the root modules: ones that have no dependencies. While doing that,
  # sort the dependent module list so that the computed load order is stable.
  module_ref_counts = {}
  for m in all_resources['scripts'].values():
    m.dependent_modules.sort(lambda x, y: cmp(x.name, y.name))
    module_ref_counts[m.name] = 0

  # Count the number of references to each module.
  def inc_ref_count(name):
    module_ref_counts[name] = module_ref_counts[name] + 1
  for m in all_resources['scripts'].values():
    for dependent_module in m.dependent_modules:
      inc_ref_count(dependent_module.name)

  # Root modules are modules with nothing depending on them.
  root_modules = [all_resources['scripts'][name]
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
