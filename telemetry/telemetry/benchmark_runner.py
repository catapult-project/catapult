# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Parses the command line, discovers the appropriate benchmarks, and runs them.

Handles benchmark configuration, but all the logic for
actually running the benchmark is in Benchmark and StoryRunner."""

from telemetry import command_line


# DEPRECATED: Clients should directly import from telemetry.command_line
# TODO(crbug.com/981349): remove when no longer used.
main = command_line.main
