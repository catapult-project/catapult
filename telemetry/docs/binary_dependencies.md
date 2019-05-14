<!-- Copyright 2019 The Chromium Authors. All rights reserved.
     Use of this source code is governed by a BSD-style license that can be
     found in the LICENSE file.
-->

# Telemetry binary dependencies

Telemetry needs some third-party binaries to run. They are stored in Google
Cloud in `chromium-telemetry` bucket, and downloaded when necessary.

You can add and update binaries via `telemetry/bin/update_telemetry_dependency`
script.

Below you can find information on some of the dependencies:

## `trace_processor_shell`
A tool used to convert collected traces in newer perfetto protobuf format to
a legacy json format.
[Source code](https://android.googlesource.com/platform/external/perfetto/+/refs/heads/master/src/trace_processor/)

