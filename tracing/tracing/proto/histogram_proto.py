# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  from tracing import histogram_pb2
  HAS_PROTO = True
except ImportError:
  HAS_PROTO = False


def _EnsureProto():
  """Ensures histogram_pb.py is in the PYTHONPATH.

  If the assert fails here, it means your script doesn't ensure histogram_pb2.py
  is generated and is in the PYTHONPATH. To fix this, depend on the GN rule
  in BUILD.gn and ensure the script gets the out/Whatever/pyproto dir in its
  PYTHONPATH (for instance by making your script take a --out-dir=out/Whatever
  flag).
  """
  assert HAS_PROTO, ('Tried to use histogram protos, but missing '
                     'histogram_pb2.py. You could try cd tracing && make.')


def Pb2():
  """Resolves the histogram proto stub.

  Where you would use histogram_pb2.X, instead do histogram_proto.Pb2().X.
  """
  _EnsureProto()
  return histogram_pb2


if HAS_PROTO:
  PROTO_UNIT_MAP = {
      histogram_pb2.MS: 'ms',
      histogram_pb2.MS_BEST_FIT_FORMAT: 'msBestFitFormat',
      histogram_pb2.TS_MS: 'tsMs',
      histogram_pb2.N_PERCENT: 'n%',
      histogram_pb2.SIZE_IN_BYTES: 'sizeInBytes',
      histogram_pb2.BYTES_PER_SECOND: 'bytesPerSecond',
      histogram_pb2.J: 'J',
      histogram_pb2.W: 'W',
      histogram_pb2.A: 'A',
      histogram_pb2.V: 'V',
      histogram_pb2.HERTZ: 'Hz',
      histogram_pb2.UNITLESS: 'unitless',
      histogram_pb2.COUNT: 'count',
      histogram_pb2.SIGMA: 'sigma',
  }

  PROTO_IMPROVEMENT_DIRECTION_MAP = {
      histogram_pb2.BIGGER_IS_BETTER: 'biggerIsBetter',
      histogram_pb2.SMALLER_IS_BETTER: 'smallerIsBetter',
  }


def UnitFromProto(proto_unit):
  _EnsureProto()
  direction = proto_unit.improvement_direction
  unit = PROTO_UNIT_MAP[proto_unit.unit]
  if direction and direction != histogram_pb2.NOT_SPECIFIED:
    unit += '_' + PROTO_IMPROVEMENT_DIRECTION_MAP[direction]

  return unit
