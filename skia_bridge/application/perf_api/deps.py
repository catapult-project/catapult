# Copyright 2024 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from application.perf_api.clients import gitiles_client
from flask import Blueprint, request, make_response
from application.perf_api import auth_helper

blueprint = Blueprint('deps', __name__)

ALLOWED_CLIENTS = [
    'ashwinpv@google.com',
    'jeffyoon@google.com',
    'haowoo@google.com',
    'sunxiaodi@google.com',
    # Chrome (public) skia instance service account
    'perf-chrome-public@skia-infra-public.iam.gserviceaccount.com',
    # Chrome (internal) skia instance service account
    'perf-chrome-internal@skia-infra-corp.iam.gserviceaccount.com',
]

DEPS_MALFORMATTED_ERROR = 'DEPS is malformatted.'

@blueprint.route('', methods=['GET'])
def GetDepsHandler():
  is_authorized, _ = auth_helper.AuthorizeBearerToken(request, ALLOWED_CLIENTS)
  if not is_authorized:
    return 'Unauthorized', 401

  repository_url = request.args.get('repository_url')
  if not repository_url:
    return 'Repository url is required in the request', 400

  git_hash = request.args.get('git_hash')
  if not git_hash:
    return 'Git hash is required in the request', 400

  try:
    client = gitiles_client.GitilesClient()
    content = client.GetGitDepsJSON(repository_url, git_hash)
    return content
  except NotImplementedError as e:
    # This means that the format of the requested DEPS is invalid.
    logging.exception(e)
    return DEPS_MALFORMATTED_ERROR, 400
  except Exception as e:
    logging.exception(e)
    raise e

