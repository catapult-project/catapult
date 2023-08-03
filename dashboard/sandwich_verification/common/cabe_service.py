# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

import grpc
import cabe_grpc.service_pb2_grpc as cabe_grpc
import cabe_grpc.service_pb2 as cabe_pb
import cabe_grpc.spec_pb2 as cabe_spec_pb

import google.auth
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests

_CABE_SERVER_ADDRESS = 'cabe.skia.org'
_CABE_USE_PLAINTEXT = False

def GetAnalysis(job_id, benchmark_name, measurment_name):
  "Return a TryJob CABE Analysis as a list."
  request = google_auth_transport_requests.Request()

  if _CABE_USE_PLAINTEXT:
    channel = grpc.insecure_channel(_CABE_SERVER_ADDRESS)
  else:
    credentials, _ = google.auth.default()
    channel = google_auth_transport_grpc.secure_authorized_channel(
        credentials=credentials, request=request, target=_CABE_SERVER_ADDRESS)

  try:
    stub = cabe_grpc.AnalysisStub(channel)
    bspec = cabe_spec_pb.Benchmark(name=benchmark_name, workload=[measurment_name])
    aspec = cabe_spec_pb.AnalysisSpec(benchmark=[bspec])

    request = cabe_pb.GetAnalysisRequest(
      pinpoint_job_id=job_id,
      experiment_spec=cabe_spec_pb.ExperimentSpec(
        analysis=aspec
      )
    )
    response = stub.GetAnalysis(request)
    return response.results
  finally:
    channel.close()
