# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The core of this script is the CalcLoadSequence function. This function
loads the provided javascript files and figures out their dependencies by
reading the tvcm.require statements in each file. This allows us to, for
example, have a trio of modules, foo, bar and baz, where foo.js contains:

    tvcm.require('bar');

and bar.js contains:

    tvcm.require('baz');

If these three modules are in the current directory, then:

    CalcLoadSequence(['foo'], '.')

Will return the correct sequence in which to load these modules based on these
dependencies, which is: [Module('baz'), Module('bar'), Module('foo')].

"""

import os

from tvcm import module
from tvcm import resource_loader


def CalcLoadSequence(filenames, project):
  """Given a list of starting javascript files, figure out all the Module
  objects that need to be loaded to satisfy their dependencies.

  The javascript files should specify their dependencies in a format that is
  textually equivalent to tvcm/__init__.js' require syntax, namely:

      tvcm.require(module1);
      tvcm.require(module2);
      tvcm.requireStylesheet(stylesheet);

  Args:
    filenames: A list of starting file paths for trace viewer modules.

  Returns:
    A list of Module objects in the order that they should be loaded.
  """
  if os.path.join('tvcm', '__init__.js') not in filenames:
    filenames = list(filenames)
    filenames.insert(0, os.path.join('tvcm', '__init__.js'))
  return CalcLoadSequenceInternal(filenames, project)


def CalcLoadSequenceInternal(filenames, project):
  """Helper function for CalcLoadSequence.

  Args:
    filenames: A list of starting file paths for trace viewer modules.
    project : A tvcm.Project

  Returns:
    A list of Module objects in the list that they should be loaded.
  """
  loader = resource_loader.ResourceLoader(project)
  initial_module_name_indices = {}
  for filename in filenames:
    m = loader.LoadModule(module_filename=filename)
    if m.name not in initial_module_name_indices:
      initial_module_name_indices[m.name] = len(initial_module_name_indices)

  # Find the root modules: ones that have no dependencies. While doing that,
  # sort the dependent module list so that the computed load order is stable.
  module_ref_counts = {}
  for m in loader.loaded_modules.values():
    m.dependent_modules.sort(lambda x, y: cmp(x.name, y.name))
    module_ref_counts[m.name] = 0

  # Count the number of references to each module.
  def IncRefCount(name):
    module_ref_counts[name] = module_ref_counts[name] + 1
  for m in loader.loaded_modules.values():
    for dependent_module in m.dependent_modules:
      IncRefCount(dependent_module.name)

  # Root modules are modules with nothing depending on them.
  root_modules = [loader.loaded_modules[name]
                  for name, ref_count in module_ref_counts.items()
                  if ref_count == 0]

  # Sort root_modules by the order they were originally requested,
  # then sort everything else by name.
  def CompareRootModule(x, y):
    n = len(initial_module_name_indices)
    iX = initial_module_name_indices.get(x.name, n)
    iY = initial_module_name_indices.get(y.name, n)
    if cmp(iX, iY) != 0:
      return cmp(iX, iY)
    return cmp(x.name, y.name)
  root_modules.sort(CompareRootModule)

  already_loaded_set = set()
  load_sequence = []
  for m in root_modules:
    m.ComputeLoadSequenceRecursive(load_sequence, already_loaded_set)
  return load_sequence
