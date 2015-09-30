# -*- coding: utf-8 -*-
# Copyright 2011 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper module for Google Cloud Storage project IDs."""

from __future__ import absolute_import

import boto

from gslib.cloud_api import ProjectIdException

GOOG_PROJ_ID_HDR = 'x-goog-project-id'


def PopulateProjectId(project_id=None):
  """Fills in a project_id from the boto config file if one is not provided."""
  if not project_id:
    default_id = boto.config.get_value('GSUtil', 'default_project_id')
    if not default_id:
      raise ProjectIdException('MissingProjectId')
    return default_id
  return project_id
