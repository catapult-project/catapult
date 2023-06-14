# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

import grpc
import cabe_grpc.service_pb2_grpc as cabe_grpc
import cabe_grpc.service_pb2 as cabe_pb

from google.auth import compute_engine
from google.auth.transport import grpc as google_auth_transport_grpc
from google.auth.transport import requests as google_auth_transport_requests

_CABE_SERVER_ADDRESS = 'cabe.skia.org'
_CABE_USE_PLAINTEXT = False

def GetAnalysis(job_id):
  "Return a TryJob CABE Analysis as a list."
  request = google_auth_transport_requests.Request()

  if _CABE_USE_PLAINTEXT:
    channel = grpc.insecure_channel(_CABE_SERVER_ADDRESS)
  else:
    credentials = compute_engine.Credentials()
    channel = google_auth_transport_grpc.secure_authorized_channel(
        credentials=credentials, request=request, target=_CABE_SERVER_ADDRESS)

  try:
    stub = cabe_grpc.AnalysisStub(channel)
    request = cabe_pb.GetAnalysisRequest(pinpoint_job_id=job_id)
    response = stub.GetAnalysis(request)
    return response.results
  finally:
    channel.close()
