# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import hashlib
import logging
import os
import re
import shutil
import subprocess

from telemetry.core.platform.profiler import android_prebuilt_profiler_helper


_TEXT_SECTION = '.text'


def _ElfSectionMd5Sum(elf_file, section):
  result = subprocess.check_output(
      'readelf -p%s "%s" | md5sum' % (section, elf_file), shell=True)
  return result.split(' ', 1)[0]


def _FindMatchingUnstrippedLibraryOnHost(device, lib):
  out_path = os.path.join(os.environ.get('CHROMIUM_OUT_DIR', 'out'), 'Release')
  lib_base = os.path.basename(lib)

  device_md5 = device.old_interface.RunShellCommandWithSU('md5 "%s"' % lib)[0]
  device_md5 = device_md5.split(' ', 1)[0]

  # First find a matching stripped library on the host. This avoids the need to
  # pull the stripped library from the device, which can take tens of seconds.
  host_lib_pattern = os.path.join(out_path, '*_apk', 'libs', '*', lib_base)
  for stripped_host_lib in glob.glob(host_lib_pattern):
    with open(stripped_host_lib) as f:
      host_md5 = hashlib.md5(f.read()).hexdigest()
      if host_md5 == device_md5:
        break
  else:
    return None

  # The corresponding unstripped library will be under out/Release/lib.
  unstripped_host_lib = os.path.join(out_path, 'lib', lib_base)

  # Make sure the unstripped library matches the stripped one. We do this
  # by comparing the hashes of text sections in both libraries. This isn't an
  # exact guarantee, but should still give reasonable confidence that the
  # libraries are compatible.
  # TODO(skyostil): Check .note.gnu.build-id instead once we're using
  # --build-id=sha1.
  # pylint: disable=W0631
  if (_ElfSectionMd5Sum(unstripped_host_lib, _TEXT_SECTION) !=
      _ElfSectionMd5Sum(stripped_host_lib, _TEXT_SECTION)):
    return None
  return unstripped_host_lib


# Ignored directories for libraries that aren't useful for symbolization.
_IGNORED_LIB_PATHS = [
  '/data/dalvik-cache',
  '/tmp'
]


def GetRequiredLibrariesForPerfProfile(profile_file):
  """Returns the set of libraries necessary to symbolize a given perf profile.

  Args:
    profile_file: Path to perf profile to analyse.

  Returns:
    A set of required library file names.
  """
  with open(os.devnull, 'w') as dev_null:
    perf = subprocess.Popen(['perf', 'script', '-i', profile_file],
                             stdout=dev_null, stderr=subprocess.PIPE)
    _, output = perf.communicate()
  missing_lib_re = re.compile(
      r'^Failed to open (.*), continuing without symbols')
  libs = set()
  for line in output.split('\n'):
    lib = missing_lib_re.match(line)
    if lib:
      lib = lib.group(1)
      path = os.path.dirname(lib)
      if any(path.startswith(ignored_path)
             for ignored_path in _IGNORED_LIB_PATHS) or path == '/':
        continue
      libs.add(lib)
  return libs


def CreateSymFs(device, symfs_dir, libraries, use_symlinks=True):
  """Creates a symfs directory to be used for symbolizing profiles.

  Prepares a set of files ("symfs") to be used with profilers such as perf for
  converting binary addresses into human readable function names.

  Args:
    device: DeviceUtils instance identifying the target device.
    symfs_dir: Path where the symfs should be created.
    libraries: Set of library file names that should be included in the symfs.
    use_symlinks: If True, link instead of copy unstripped libraries into the
      symfs. This will speed up the operation, but the resulting symfs will no
      longer be valid if the linked files are modified, e.g., by rebuilding.

  Returns:
    The absolute path to the kernel symbols within the created symfs.
  """
  logging.info('Building symfs into %s.' % symfs_dir)

  mismatching_files = {}
  for lib in libraries:
    device_dir = os.path.dirname(lib)
    output_dir = os.path.join(symfs_dir, device_dir[1:])
    if not os.path.exists(output_dir):
      os.makedirs(output_dir)
    output_lib = os.path.join(output_dir, os.path.basename(lib))

    if lib.startswith('/data/app-lib/'):
      # If this is our own library instead of a system one, look for a matching
      # unstripped library under the out directory.
      unstripped_host_lib = _FindMatchingUnstrippedLibraryOnHost(device, lib)
      if not unstripped_host_lib:
        logging.warning('Could not find symbols for %s.' % lib)
        logging.warning('Is the correct output directory selected '
                        '(CHROMIUM_OUT_DIR)? Did you install the APK after '
                        'building?')
        continue
      if use_symlinks:
        if os.path.lexists(output_lib):
          os.remove(output_lib)
        os.symlink(os.path.abspath(unstripped_host_lib), output_lib)
      # Copy the unstripped library only if it has been changed to avoid the
      # delay. Add one second to the modification time to guard against file
      # systems with poor timestamp resolution.
      elif not os.path.exists(output_lib) or \
          (os.stat(unstripped_host_lib).st_mtime >
           os.stat(output_lib).st_mtime + 1):
        logging.info('Copying %s to %s' % (unstripped_host_lib, output_lib))
        shutil.copy2(unstripped_host_lib, output_lib)
    else:
      # Otherwise save a copy of the stripped system library under the symfs so
      # the profiler can at least use the public symbols of that library. To
      # speed things up, only pull files that don't match copies we already
      # have in the symfs.
      if not device_dir in mismatching_files:
        changed_files = device.old_interface.GetFilesChanged(output_dir,
                                                             device_dir)
        mismatching_files[device_dir] = [
            device_path for _, device_path in changed_files]

      if not os.path.exists(output_lib) or lib in mismatching_files[device_dir]:
        logging.info('Pulling %s to %s' % (lib, output_lib))
        device.old_interface.PullFileFromDevice(lib, output_lib)

  # Also pull a copy of the kernel symbols.
  output_kallsyms = os.path.join(symfs_dir, 'kallsyms')
  if not os.path.exists(output_kallsyms):
    device.old_interface.PullFileFromDevice('/proc/kallsyms', output_kallsyms)
  return output_kallsyms


def PrepareDeviceForPerf(device):
  """Set up a device for running perf.

  Args:
    device: DeviceUtils instance identifying the target device.

  Returns:
    The path to the installed perf binary on the device.
  """
  android_prebuilt_profiler_helper.InstallOnDevice(device, 'perf')
  # Make sure kernel pointers are not hidden.
  device.old_interface.SetProtectedFileContents(
      '/proc/sys/kernel/kptr_restrict', '0')
  return android_prebuilt_profiler_helper.GetDevicePath('perf')
