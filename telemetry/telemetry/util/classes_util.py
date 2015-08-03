# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import discover
from telemetry.internal.util import camel_case


def DiscoverClasses(start_dir, top_level_dir, base_class,
                    directly_constructable=False):
  return discover.DiscoverClasses(start_dir, top_level_dir, base_class,
                                  directly_constructable=directly_constructable)

def DiscoverClassesByClassName(
    start_dir, top_level_dir, base_class, directly_constructable=False):
  classes_dict = {}
  classes = discover.DiscoverClasses(
      start_dir, top_level_dir, base_class,
      directly_constructable=directly_constructable)
  for class_obj in classes:
    classes_dict[camel_case.ToUnderscore(class_obj.__name__)] = class_obj
  return classes_dict

def MaybeGetInstanceOfClass(target, start_dir, top_level_dir, cls):
  classes = DiscoverClassesByClassName(
      start_dir, top_level_dir, cls, directly_constructable=True)
  return classes[target]() if target in classes else None
