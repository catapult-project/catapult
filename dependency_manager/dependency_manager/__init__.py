# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys


CATAPULT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CATAPULT_THIRD_PARTY_PATH = os.path.join(CATAPULT_PATH, 'third_party')
DEPENDENCY_MANAGER_PATH = os.path.join(CATAPULT_PATH, 'dependency_manager')


def _AddDirToPythonPath(*path_parts):
  # pylint: disable=no-value-for-parameter
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    sys.path.insert(0, path)


_AddDirToPythonPath(CATAPULT_PATH, 'common', 'py_utils')
_AddDirToPythonPath(CATAPULT_THIRD_PARTY_PATH, 'mock')
_AddDirToPythonPath(CATAPULT_THIRD_PARTY_PATH, 'six')
_AddDirToPythonPath(DEPENDENCY_MANAGER_PATH)


# pylint: disable=unused-import,wrong-import-position
from .archive_info import ArchiveInfo
from .base_config import BaseConfig
from .cloud_storage_info import CloudStorageInfo
from .dependency_info import DependencyInfo
from .exceptions import CloudStorageError
from .exceptions import CloudStorageUploadConflictError
from .exceptions import EmptyConfigError
from .exceptions import FileNotFoundAtError
from .exceptions import NoPathFoundError
from .exceptions import ReadWriteError
from .exceptions import UnsupportedConfigFormatError
from .local_path_info import LocalPathInfo
from .manager import DependencyManager
# pylint: enable=unused-import
