# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import tvcm

from telemetry.web_components import web_components_project


def Main(port, args):
  parser = optparse.OptionParser()
  _, args = parser.parse_args(args)

  project = web_components_project.WebComponentsProject()
  server = tvcm.DevServer(
      port=port, project=project)

  def IsTestModuleResourcePartOfTelemetry(module_resource):
    return module_resource.absolute_path.startswith(project.telemetry_path)

  server.test_module_resource_filter = IsTestModuleResourcePartOfTelemetry
  return server.serve_forever()
