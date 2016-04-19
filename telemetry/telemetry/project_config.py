# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class ProjectConfig(object):
  """Contains information about the benchmark runtime environment.

  Attributes:
    top_level_dir: A dir that contains benchmark, page test, and/or story
        set dirs and associated artifacts.
    benchmark_dirs: A list of dirs containing benchmarks.
    benchmark_aliases: A dict of name:alias string pairs to be matched against
        exactly during benchmark selection.
    client_config: A path to a ProjectDependencies json file.
    client_configs: A list of paths to a ProjectDependencies json files.
    default_chrome_root: A path to chromium source directory. Many telemetry
      features depend on chromium source tree's presence and those won't work
      in case this is not specified.
  """
  # TODO(nednguyen): remove |client_config| param once all the call sites are
  # updated to use |client_configs|. (catapult:#2259, crbug.com/580919)
  def __init__(self, top_level_dir, benchmark_dirs=None,
               benchmark_aliases=None, client_config=None, client_configs=None,
               default_chrome_root=None):
    self._top_level_dir = top_level_dir
    self._benchmark_dirs = benchmark_dirs or []
    self._benchmark_aliases = benchmark_aliases or dict()
    self._default_chrome_root = default_chrome_root
    if client_config:
      assert not client_configs, (
          'Cannot specify both client_config & client_configs')
      self._client_configs = [client_config]
    else:
      self._client_configs = client_configs or []

  @property
  def top_level_dir(self):
    return self._top_level_dir

  @property
  def start_dirs(self):
    return self._benchmark_dirs

  @property
  def benchmark_dirs(self):
    return self._benchmark_dirs

  @property
  def benchmark_aliases(self):
    return self._benchmark_aliases

  @property
  def client_configs(self):
    return self._client_configs

  @property
  def default_chrome_root(self):
    return self._default_chrome_root
