# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The following benchmark and devices represents the allowlist for the
sandwich verification workflow. The current allowlist is based on the
press benchmarks and the available capacity on Pinpoint."""

# TODO: Implement the allowable configs as a class so that each benchmark
# can customize its own list of allowable stories and configurations.
ALLOWABLE_BENCHMARKS = ['jetstream2','speedometer2']
ALLOWABLE_DEVICES = [
    'android-pixel2-perf',
    'android-pixel2_webview-perf'
    'android-pixel4-perf',
    'linux-perf',
    'mac-laptop_high_end-perf',
    'mac-laptop_low_end-perf',
    'mac-m1_mini_2020-perf',
    'win-10_amd_laptop-perf',
    'win-10_laptop_low_end-perf',
    'win-10-perf',
    ]
