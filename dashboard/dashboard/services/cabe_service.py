# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

import logging

import grpc
from dashboard.services.cabe_grpc import service_pb2_grpc as cabe_grpc_pb
from dashboard.services.cabe_grpc import service_pb2 as cabe_pb

import google.auth
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
    credentials, project_id = google.auth.default()
    logging.info("using default credentials for project_id: %s", project_id)
    channel = google_auth_transport_grpc.secure_authorized_channel(
        credentials=credentials, request=request, target=_CABE_SERVER_ADDRESS)

  try:
    stub = cabe_grpc_pb.AnalysisStub(channel)
    request = cabe_pb.GetAnalysisRequest(pinpoint_job_id=job_id)
    response = stub.GetAnalysis(request)
    return response.results
  finally:
    channel.close()
