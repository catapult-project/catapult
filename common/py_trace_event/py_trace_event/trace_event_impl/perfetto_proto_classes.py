# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

""" Classes representing perfetto trace protobuf messages.

This module makes use of neither python-protobuf library nor python classes
compiled from .proto definitions, because currently there's no way to
deploy those to all the places where telemetry is run.

TODO(crbug.com/944078): Remove this module after the python-protobuf library
is deployed to all the bots.

Definitions of perfetto messages can be found here:
https://android.googlesource.com/platform/external/perfetto/+/refs/heads/master/protos/perfetto/trace/
"""

import encoder
import wire_format


class TracePacket(object):
  def __init__(self):
    self.interned_data = None
    self.thread_descriptor = None
    self.incremental_state_cleared = None
    self.track_event = None
    self.trusted_packet_sequence_id = None
    self.chrome_benchmark_metadata = None

  def encode(self):
    parts = []
    if self.trusted_packet_sequence_id is not None:
      writer = encoder.UInt32Encoder(10, False, False)
      writer(parts.append, self.trusted_packet_sequence_id)
    if self.track_event is not None:
      tag = encoder.TagBytes(11, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.track_event.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]
    if self.interned_data is not None:
      tag = encoder.TagBytes(12, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.interned_data.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]
    if self.incremental_state_cleared is not None:
      writer = encoder.BoolEncoder(41, False, False)
      writer(parts.append, self.incremental_state_cleared)
    if self.thread_descriptor is not None:
      tag = encoder.TagBytes(44, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.thread_descriptor.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]
    if self.chrome_benchmark_metadata is not None:
      tag = encoder.TagBytes(48, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.chrome_benchmark_metadata.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]

    return b"".join(parts)


class InternedData(object):
  def __init__(self):
    self.event_category = None
    self.legacy_event_name = None

  def encode(self):
    parts = []
    if self.event_category is not None:
      tag = encoder.TagBytes(1, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.event_category.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]
    if self.legacy_event_name is not None:
      tag = encoder.TagBytes(2, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.legacy_event_name.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]

    return b"".join(parts)


class EventCategory(object):
  def __init__(self):
    self.iid = None
    self.name = None

  def encode(self):
    if (self.iid is None or self.name is None):
      raise RuntimeError("Missing mandatory fields.")

    parts = []
    writer = encoder.UInt32Encoder(1, False, False)
    writer(parts.append, self.iid)
    writer = encoder.StringEncoder(2, False, False)
    writer(parts.append, self.name)

    return b"".join(parts)


LegacyEventName = EventCategory


class ThreadDescriptor(object):
  def __init__(self):
    self.pid = None
    self.tid = None
    self.reference_timestamp_us = None

  def encode(self):
    if (self.pid is None or self.tid is None or
        self.reference_timestamp_us is None):
      raise RuntimeError("Missing mandatory fields.")

    parts = []
    writer = encoder.UInt32Encoder(1, False, False)
    writer(parts.append, self.pid)
    writer = encoder.UInt32Encoder(2, False, False)
    writer(parts.append, self.tid)
    writer = encoder.Int64Encoder(6, False, False)
    writer(parts.append, self.reference_timestamp_us)

    return b"".join(parts)


class TrackEvent(object):
  def __init__(self):
    self.timestamp_absolute_us = None
    self.timestamp_delta_us = None
    self.legacy_event = None
    self.category_iids = None

  def encode(self):
    parts = []
    if self.timestamp_delta_us is not None:
      writer = encoder.Int64Encoder(1, False, False)
      writer(parts.append, self.timestamp_delta_us)
    if self.category_iids is not None:
      writer = encoder.UInt32Encoder(3, is_repeated=True, is_packed=False)
      writer(parts.append, self.category_iids)
    if self.legacy_event is not None:
      tag = encoder.TagBytes(6, wire_format.WIRETYPE_LENGTH_DELIMITED)
      data = self.legacy_event.encode()
      length = encoder._VarintBytes(len(data))
      parts += [tag, length, data]
    if self.timestamp_absolute_us is not None:
      writer = encoder.Int64Encoder(16, False, False)
      writer(parts.append, self.timestamp_absolute_us)

    return b"".join(parts)


class LegacyEvent(object):
  def __init__(self):
    self.phase = None
    self.name_iid = None

  def encode(self):
    parts = []
    if self.name_iid is not None:
      writer = encoder.UInt32Encoder(1, False, False)
      writer(parts.append, self.name_iid)
    if self.phase is not None:
      writer = encoder.Int32Encoder(2, False, False)
      writer(parts.append, self.phase)

    return b"".join(parts)


class ChromeBenchmarkMetadata(object):
  def __init__(self):
    self.benchmark_start_time_us = None
    self.story_run_time_us = None
    self.benchmark_name = None
    self.benchmark_description = None
    self.story_name = None
    self.story_tags = None
    self.story_run_index = None
    self.label = None
    self.had_failures = None

  def encode(self):
    parts = []
    if self.benchmark_start_time_us is not None:
      writer = encoder.Int64Encoder(1, False, False)
      writer(parts.append, self.benchmark_start_time_us)
    if self.story_run_time_us is not None:
      writer = encoder.Int64Encoder(2, False, False)
      writer(parts.append, self.story_run_time_us)
    if self.benchmark_name is not None:
      writer = encoder.StringEncoder(3, False, False)
      writer(parts.append, self.benchmark_name)
    if self.benchmark_description is not None:
      writer = encoder.StringEncoder(4, False, False)
      writer(parts.append, self.benchmark_description)
    if self.label is not None:
      writer = encoder.StringEncoder(5, False, False)
      writer(parts.append, self.label)
    if self.story_name is not None:
      writer = encoder.StringEncoder(6, False, False)
      writer(parts.append, self.story_name)
    if self.story_tags is not None:
      writer = encoder.StringEncoder(7, is_repeated=True, is_packed=False)
      writer(parts.append, self.story_tags)
    if self.story_run_index is not None:
      writer = encoder.Int32Encoder(8, False, False)
      writer(parts.append, self.story_run_index)
    if self.had_failures is not None:
      writer = encoder.BoolEncoder(9, False, False)
      writer(parts.append, self.had_failures)

    return b"".join(parts)


def write_trace_packet(output, trace_packet):
  tag = encoder.TagBytes(1, wire_format.WIRETYPE_LENGTH_DELIMITED)
  output.write(tag)
  binary_data = trace_packet.encode()
  encoder._EncodeVarint(output.write, len(binary_data))
  output.write(binary_data)

