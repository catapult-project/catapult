// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tracing/tracing/value/histogram_json_converter.h"

#include "third_party/protobuf/src/google/protobuf/util/json_util.h"

namespace catapult {

bool ToJson(const tracing::tracing::proto::HistogramSet& histogram_set,
            std::string* output) {
  google::protobuf::util::JsonPrintOptions json_options;
  json_options.add_whitespace = true;
  google::protobuf::util::Status status =
      google::protobuf::util::MessageToJsonString(histogram_set, output,
                                                  json_options);
  return status.ok();
}

}  // namespace catapult
