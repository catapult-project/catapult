# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from flask import Flask

from application.api.dummy import dummy

def create_app():
    app = Flask(__name__)
    app.register_blueprint(dummy, url_prefix='/')
    return app