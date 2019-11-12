# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Logging-like module for creating artifacts.

In order to actually create artifacts, RegisterArtifactImplementation must be
called from somewhere with an artifact implementation to use, otherwise
CreateArtifact will just end up logging the first 100 characters of the given
data.

This registration is automatically handled in tests that use Telemetry or typ as
their test runner, so it should only really need to be used if you are adding a
new test runner type.

Example usage:

# During test setup.
artifact_logger.RegisterArtifactImplementation(self.results)

# At any point in the test afterwards, from any module.
artifact_logger.CreateArtifact('some/crash/stack.txt', GetStackTrace())
"""

from telemetry.internal.results import (
    artifact_compatibility_wrapper as artifact_wrapper)


artifact_impl = artifact_wrapper.ArtifactCompatibilityWrapperFactory(None)


def CreateArtifact(name, data):
  """Create an artifact with the given data.

    Args:
      name: The name of the artifact, can include '/' to organize artifacts
          within a hierarchy.
      data: The data to write to the artifact.
  """
  artifact_impl.CreateArtifact(name, data)


def RegisterArtifactImplementation(artifact_implementation):
  """Register the artifact implementation used to log future artifacts.

  Args:
    artifact_implementation: The artifact implementation to use for future
        artifact creations. Must be supported in
        artifact_compatibility_wrapper.ArtifactCompatibilityWrapperFactory.
  """
  global artifact_impl  # pylint: disable=global-statement
  artifact_impl = artifact_wrapper.ArtifactCompatibilityWrapperFactory(
      artifact_implementation)
