# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import shutil
import socket
import tempfile
import unittest

from telemetry.page import profile_generator


class ProfileGeneratorUnitTest(unittest.TestCase):
  def setUp(self):
    self.test_directory = tempfile.mkdtemp()
    super(ProfileGeneratorUnitTest, self).setUp()

  def _CreateFunkyFilesAndOnePlainFile(self, sandbox_directory):
    """Create several special files and one plain file in |sandbox_directory|.
    """
    if os.path.exists(sandbox_directory):
      shutil.rmtree(sandbox_directory)

    os.mkdir(sandbox_directory)

    # Make a plain file.
    plain_filename = os.path.join(sandbox_directory, 'plain_file')
    open(plain_filename, 'a').close()

    # Make a directory.
    directory_filename = os.path.join(sandbox_directory, 'directory')
    os.mkdir(directory_filename)

    if getattr(os, 'symlink', None): # Symlinks not supported on Windows.
      # Make a symlink.
      symlink_filename = os.path.join(sandbox_directory, 'symlink')
      os.symlink(plain_filename, symlink_filename)

      # Make a broken symlink.
      nonexistant_filename = os.path.join(sandbox_directory, 'i_dont_exist')
      broken_symlink_filename = os.path.join(sandbox_directory,
          'broken_symlink')
      os.symlink(nonexistant_filename, broken_symlink_filename)

    # Make a named socket.
    if getattr(socket, 'AF_UNIX', None): # Windows doesn't support these.
      socket_filename = os.path.join(sandbox_directory, 'named_socket')
      the_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      the_socket.bind(socket_filename)

  def testIsPseudoFile(self):
    sandbox_dir = os.path.join(self.test_directory, "sandbox")
    self._CreateFunkyFilesAndOnePlainFile(sandbox_dir)

    # If we can copy the directory, we're golden!
    sandbox_dir_copy = os.path.join(self.test_directory, "sandbox_copy")
    # pylint: disable=W0212
    shutil.copytree(sandbox_dir, sandbox_dir_copy,
        ignore=profile_generator._IsPseudoFile)

    # Check that only the directory and plain file got copied.
    dir_contents = os.listdir(sandbox_dir_copy)
    dir_contents.sort()
    self.assertEqual(['directory', 'plain_file'], dir_contents)

  def tearDown(self):
    shutil.rmtree(self.test_directory)
