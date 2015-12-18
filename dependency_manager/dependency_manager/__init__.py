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
  path = os.path.abspath(os.path.join(*path_parts))
  if os.path.isdir(path) and path not in sys.path:
    sys.path.append(path)


_AddDirToPythonPath(DEPENDENCY_MANAGER_PATH)
_AddDirToPythonPath(CATAPULT_THIRD_PARTY_PATH, 'mock')
_AddDirToPythonPath(CATAPULT_PATH, 'catapult_base')


from .archive_info import ArchiveInfo
from .base_config import BaseConfig
from .cloud_storage_info import CloudStorageInfo
from .dependency_info import DependencyInfo
from .manager import DependencyManager
from .exceptions import (
    CloudStorageUploadConflictError, EmptyConfigError, FileNotFoundError,
    NoPathFoundError, ReadWriteError, UnsupportedConfigFormatError)
from .local_path_info import LocalPathInfo

