# Copyright 201 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

wct:
	xvfb-run go run ../../go/src/infra/tools/wct/wct.go  ../../go/src/infra/tools/wct/monkeypatch.go -chrome=google-chrome

wct_debug:
	go run ../../go/src/infra/tools/wct/wct.go  ../../go/src/infra/tools/wct/monkeypatch.go -chrome=google-chrome -persist
