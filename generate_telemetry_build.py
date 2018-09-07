#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate BUILD.gn to define all data required to run telemetry test.

If a file/folder of large size is added to catapult but is not needed to run
telemetry test, then it should be added to the EXCLUDED_PATHS below and rerun
this script.

This script can also run with --check to see if it needs to rerun to update
BUILD.gn.

This script can also run with --chromium and rewrite the chromium file
   //tools/perf/chrome_telemetry_build/BUILD.gn
This is for the purpose of running try jobs in chromium.

"""

import difflib
import logging
import os
import optparse
import sys

LICENSE = """# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""

DO_NOT_EDIT_WARNING = """# This file is auto-generated from
#    //third_party/catapult/generated_telemetry_build.py
# DO NOT EDIT!

"""

TELEMETRY_SUPPORT_GROUP_NAME = 'telemetry_chrome_test_support'

EXCLUDED_PATHS = [
  {
    # needed for --chromium option; can remove once this CL lands.
    "path": "BUILD.gn",
  },
  {
    "path": "common/node_runner",
  },
  {
    "path": "docs",
  },
  {
    "path": "experimental",
  },
  {
    # needed for --chromium option; can remove once this CL lands.
    "path": "generate_telemetry_build.py",
  },
  {
    "path": "telemetry/telemetry/data",
  },
  {
    "path": "telemetry/telemetry/bin",
  },
  {
    "path": "telemetry/telemetry/internal/bin",
  },
  {
    # needed for --check option
    "path": "TEMP.gn",
  },
  {
    "path": "third_party/google-endpoints",
  },
  {
    "path": "third_party/Paste",
  },
  {
    "path": "third_party/polymer2",
  },
  {
    "path": "third_party/vinn/third_party/v8/linux/arm",
    "condition": "is_chromeos",
  },
  {
    "path": "third_party/vinn/third_party/v8/linux/mips",
    "condition": "is_chromeos",
  },
  {
    "path": "third_party/vinn/third_party/v8/linux/mips64",
    "condition": "is_chromeos",
  },
  {
    "path": "third_party/vinn/third_party/v8/linux/x86_64",
    "condition": "is_linux || is_android",
  },
  {
    "path": "third_party/vinn/third_party/v8/mac",
    "condition": "is_mac",
  },
  {
    "path": "third_party/vinn/third_party/v8/win",
    "condition": "is_win",
  },
  {
    "path": "tracing/test_data",
  },
]

def GetFileCondition(rel_path):
  # Return 'true' if the file should be included; return 'false' if it should
  # be excluded; return a condition string if it should only be included if
  # the condition is true.
  processed_rel_path = rel_path.replace('\\', '/')
  for exclusion in EXCLUDED_PATHS:
    assert 'path' in exclusion
    if exclusion['path'] == processed_rel_path:
      if 'condition' in exclusion:
        return exclusion['condition']
      else:
        return 'false'
  return 'true'

def GetDirCondition(rel_path):
  # Return 'true' if the dir should be included; return 'false' if it should
  # be excluded; return a condition string if it should only be included if
  # the condition is true; return 'expand' if some files or sub-dirs under it
  # are excluded or conditionally included, so the parser needs to go inside
  # the dir and process further.
  processed_rel_path = rel_path.replace('\\', '/')
  for exclusion in EXCLUDED_PATHS:
    assert 'path' in exclusion
    if exclusion['path'] == processed_rel_path:
      if 'condition' in exclusion:
        return exclusion['condition']
      else:
        return 'false'
    elif exclusion['path'].startswith(processed_rel_path + '/'):
      return 'expand'
  return 'true'

def WriteLists(lists, conditional_lists, build_file, path_prefix):
  first_entry = True
  for path_list in lists:
    for path in path_list:
      path = path.replace('\\', '/')
      if path_prefix:
        path = path_prefix + path
      if first_entry:
        build_file.write('  data += [\n')
        first_entry = False
      build_file.write('    "%s",\n' % path)
  if not first_entry:
    build_file.write('  ]\n\n')
  for conditional_list in conditional_lists:
    for entry in conditional_list:
      assert 'path' in entry
      assert 'condition' in entry
      path = entry['path'].replace('\\', '/')
      if path_prefix:
        path = path_prefix + path
      build_file.write("""  if (%s) {
    data += [ "%s" ]
  }

""" % (entry['condition'], path))

def ProcessDir(root_path, path, build_file, path_prefix):
  # Write all dirs and files directly under |path| unless they are excluded
  # or need to be processed further because some of their children are excldued
  # or conditionally included.
  # Return a list of dirs that needs to processed further.
  logging.debug('GenerateList for ' + path)
  entry_list = os.listdir(path)
  entry_list.sort()
  file_list = []
  dir_list = []
  conditional_list = []
  expand_list = []
  for entry in entry_list:
    full_path = os.path.join(path, entry)
    rel_path = os.path.relpath(full_path, root_path)
    if (entry.startswith('.') or entry.endswith('~') or
        entry.endswith('.pyc') or entry.endswith('#')):
      logging.debug('ignored ' + rel_path)
      continue
    if os.path.isfile(full_path):
      condition = GetFileCondition(rel_path)
      if condition == 'true':
        file_list.append(rel_path)
      elif condition == 'false':
        logging.debug('excluded ' + rel_path)
        continue
      else:
        conditional_list.append({
          "condition": condition,
          "path": rel_path,
        });
    elif os.path.isdir(full_path):
      condition = GetDirCondition(rel_path)
      if condition == 'true':
        dir_list.append(rel_path + '/')
      elif condition == 'false':
        logging.debug('excluded ' + rel_path)
      elif condition == 'expand':
        expand_list.append(full_path)
      else:
        conditional_list.append({
          "condition": condition,
          "path": rel_path + '/',
        });
    else:
      assert False
  WriteLists([file_list, dir_list], [conditional_list],
             build_file, path_prefix)
  return expand_list

def WriteBuildFileHeader(build_file):
  build_file.write(LICENSE)
  build_file.write(DO_NOT_EDIT_WARNING)
  build_file.write('import("//build/config/compiler/compiler.gni")\n\n')

def WriteBuildFileBody(build_file, root_path, path_prefix):
  build_file.write("""group("%s") {
  testonly = true
  data = []

""" % TELEMETRY_SUPPORT_GROUP_NAME)

  candidates = [root_path]
  while len(candidates) > 0:
    candidate = candidates.pop(0)
    more = ProcessDir(root_path, candidate, build_file, path_prefix)
    candidates.extend(more)

  build_file.write("}")

def GenerateBuildFile(root_path, output_path, chromium):
  CHROMIUM_GROUP = 'group("telemetry_chrome_test_without_chrome")'
  CATAPULT_PREFIX = '//third_party/catapult'
  CATAPULT_GROUP_NAME = CATAPULT_PREFIX + ':' + TELEMETRY_SUPPORT_GROUP_NAME
  TELEMETRY_SUPPORT_GROUP = 'group("%s")' % TELEMETRY_SUPPORT_GROUP_NAME
  if chromium:
    build_file = open(output_path, 'r+')
    contents = build_file.readlines()
    build_file.seek(0)
    remove_telemetry_support_group = False
    for line in contents:
      if TELEMETRY_SUPPORT_GROUP in line:
        # --chromium has already run once, so remove the previously inserted
        # TELEMETRY_SUPPORT_GROUP so we could add an updated one.
        remove_telemetry_support_group = True
        continue
      if remove_telemetry_support_group:
        if line == '}\n':
          remove_telemetry_support_group = False
        continue
      if CHROMIUM_GROUP in line:
        WriteBuildFileBody(build_file, root_path, CATAPULT_PREFIX + '/')
        build_file.write('\n')
      elif CATAPULT_GROUP_NAME in line:
        line = line.replace(CATAPULT_GROUP_NAME,
                            ':' + TELEMETRY_SUPPORT_GROUP_NAME)
      build_file.write(line)
    build_file.close()
  else:
    build_file = open(output_path, 'w')
    WriteBuildFileHeader(build_file)
    WriteBuildFileBody(build_file, root_path, None)
    build_file.close()

def CheckForChanges():
  # Return 0 if no changes are detected; return 1 otherwise.
  root_path = os.path.dirname(os.path.realpath(__file__))
  temp_path = os.path.join(root_path, "TEMP.gn")
  GenerateBuildFile(root_path, temp_path, chromium=False)

  ref_path = os.path.join(root_path, "BUILD.gn")
  if not os.path.exists(ref_path):
    logging.error("Can't localte BUILD.gn!")
    return 1

  temp_file = open(temp_path, 'r')
  temp_content = temp_file.readlines()
  temp_file.close()
  os.remove(temp_path)
  ref_file = open(ref_path, 'r')
  ref_content = ref_file.readlines()
  ref_file.close()

  diff = difflib.unified_diff(temp_content, ref_content, fromfile=temp_path,
                              tofile=ref_path, lineterm='')
  diff_data = []
  for line in diff:
    diff_data.append(line)
  if len(diff_data) > 0:
    logging.error('Diff found. Please rerun generate_telemetry_build.py.')
    logging.debug('\n' + ''.join(diff_data))
    return 1
  logging.debug('No diff found. Everything is good.')
  return 0


def main(argv):
  parser = optparse.OptionParser()
  parser.add_option("-v", "--verbose", action="store_true", default=False,
                    help="print out debug information")
  parser.add_option("-c", "--check", action="store_true", default=False,
                    help="generate a temporary build file and compare if it "
                    "is the same as the current BUILD.gn")
  parser.add_option("--chromium", action="store_true", default=False,
                    help="generate the build file into chromium workspace. "
                    "This is for the purpose of running try jobs in Chrome.")
  (options, _) = parser.parse_args(args=argv)
  if options.verbose:
    logging.basicConfig(level=logging.DEBUG)

  if options.check:
    return CheckForChanges()
  if options.chromium:
    root_path = os.path.dirname(os.path.realpath(__file__))
    output_path = os.path.join(
        root_path, "../../tools/perf/chrome_telemetry_build/BUILD.gn")
    GenerateBuildFile(root_path, output_path, chromium=True)
  else:
    root_path = os.path.dirname(os.path.realpath(__file__))
    output_path = os.path.join(root_path, "BUILD.gn")
    GenerateBuildFile(root_path, output_path, chromium=False)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
