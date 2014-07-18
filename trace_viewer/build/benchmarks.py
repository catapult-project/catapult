# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import cProfile, pstats, StringIO
import inspect
import optparse
import sys

from trace_viewer import trace_viewer_project

class Bench(object):
  def SetUp(self):
    pass
  def Run(self):
    pass
  def TearDown(self):
    pass

class CalcDepsBench(Bench):
  def Run(self):
    project = trace_viewer_project.TraceViewerProject()
    load_sequence = project.CalcLoadSequenceForAllModules()

class FindAllModuleFilenamesBench(Bench):
  def Run(self):
    project = trace_viewer_project.TraceViewerProject()
    filenames = project.FindAllModuleFilenames()

class DoGenerate(Bench):
  def SetUp():
    self.project = trace_viewer_project.TraceViewerProject()
    self.load_sequence = project.CalcLoadSequenceForAllModules()

  def Run(self):
    self.deps = generate.GenerateDepsJS(
      self.load_sequence, self.project)


def Main(args):
  parser = optparse.OptionParser()
  parser.add_option('--repeat-count', type='int',
                    default=10)
  options, args = parser.parse_args(args)

  benches = [g for g in globals().values()
             if g != Bench and inspect.isclass(g) and Bench in inspect.getmro(g)]
  if len(args) != 1:
    sys.stderr.write('\n'.join([b.__name__ for b in benches]))
    return 1

  b = [b for b in benches if b.__name__ == args[0]]
  if len(b) != 1:
    sys.stderr.write('Oops')
    return 1

  bench = b[0]()
  bench.SetUp()
  try:
    pr = cProfile.Profile()
    pr.enable(builtins=False)
    for i in range(options.repeat_count):
      bench.Run()
    pr.disable()
    s = StringIO.StringIO()

    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()
    print s.getvalue()
    return 0
  finally:
    bench.TearDown()

if __name__ == '__main__':
  sys.exit(Main(sys.argv[1:]))
