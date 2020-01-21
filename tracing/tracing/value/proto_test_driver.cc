// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "tracing/tracing/proto/histogram.pb.h"
#include "tracing/tracing/value/histogram.h"

// This program is useful for testing the new proto format in JSON.
// TODO(https://crbug.com/1029452): Remove once the format is stable?.

namespace catapult {

namespace proto = tracing::tracing::proto;

proto::UnitAndDirection UnitWhatever() {
  proto::UnitAndDirection unit;
  unit.set_unit(proto::UNITLESS);
  unit.set_improvement_direction(proto::NOT_SPECIFIED);
  return unit;
}

void ExampleProtoToJson() {
  proto::HistogramSet histogram_set;

  proto::Histogram* histogram = histogram_set.add_histograms();
  histogram->set_name("name!");
  proto::UnitAndDirection* unit = histogram->mutable_unit();
  *unit = UnitWhatever();

  proto::BinBoundaries* bin_boundaries = histogram->mutable_bin_boundaries();
  bin_boundaries->set_first_bin_boundary(17);
  proto::BinBoundarySpec* bin_boundary_spec = bin_boundaries->add_bin_specs();
  bin_boundary_spec->set_bin_boundary(18);

  bin_boundary_spec = bin_boundaries->add_bin_specs();
  proto::BinBoundaryDetailedSpec* detailed_spec =
      bin_boundary_spec->mutable_bin_spec();
  detailed_spec->set_boundary_type(proto::BinBoundaryDetailedSpec::EXPONENTIAL);
  detailed_spec->set_maximum_bin_boundary(19);
  detailed_spec->set_num_bin_boundaries(20);

  histogram->set_description("description!");

  proto::DiagnosticMap* diagnostics = histogram->mutable_diagnostics();
  auto diagnostic_map = diagnostics->mutable_diagnostic_map();
  proto::Diagnostic stories;
  stories.set_shared_diagnostic_guid("923e4567-e89b-12d3-a456-426655440000");
  (*diagnostic_map)["stories"] = stories;
  proto::Diagnostic masters;
  masters.set_shared_diagnostic_guid("04399b74-913d-4afa-b464-d8a43f7729ad");
  (*diagnostic_map)["masters"] = masters;
  proto::Diagnostic bots;
  bots.set_shared_diagnostic_guid("f7f17394-fa4a-481e-86bd-a82cd55935a7");
  (*diagnostic_map)["bots"] = bots;
  proto::Diagnostic benchmarks;
  benchmarks.set_shared_diagnostic_guid("5e416298-e572-463d-9a3d-5f881d1cb200");
  (*diagnostic_map)["benchmarks"] = benchmarks;
  proto::Diagnostic point_id;
  point_id.set_shared_diagnostic_guid("88ea36c7-6dcb-4ba8-ba56-1979de05e16f");
  (*diagnostic_map)["pointId"] = point_id;

  proto::Diagnostic generic_set_diag;
  proto::GenericSet* generic_set = generic_set_diag.mutable_generic_set();
  generic_set->add_values("\"some value\"");
  (*diagnostic_map)["whatever"] = generic_set_diag;

  histogram->add_sample_values(21.0);
  histogram->add_sample_values(22.0);
  histogram->add_sample_values(23.0);

  histogram->set_max_num_sample_values(3);

  histogram->set_num_nans(1);
  proto::DiagnosticMap* nan_diagnostics = histogram->add_nan_diagnostics();
  diagnostic_map = nan_diagnostics->mutable_diagnostic_map();
  // Reuse for laziness.
  (*diagnostic_map)["some nan diagnostic"] = generic_set_diag;

  proto::RunningStatistics* running = histogram->mutable_running();
  running->set_count(4);
  running->set_max(23.0);
  running->set_meanlogs(1.0);  // ??
  running->set_mean(22.0);
  running->set_min(21.0);
  running->set_sum(66.0);
  running->set_variance(1.0);

  auto bin_map = histogram->mutable_all_bins();
  proto::Bin bin;
  bin.set_bin_count(24);
  proto::DiagnosticMap* bin_diagnostics = bin.add_diagnostic_maps();
  diagnostic_map = bin_diagnostics->mutable_diagnostic_map();
  (*diagnostic_map)["some bin diagnostic"] = generic_set_diag;
  (*bin_map)[0] = bin;

  proto::SummaryOptions* options = histogram->mutable_summary_options();
  options->set_nans(true);
  options->add_percentile(90.0);
  options->add_percentile(95.0);
  options->add_percentile(99.0);

  // Note that GenericSet values need to be JSON, so 1234 is an int, "1234" is
  // a string, and "abcd" is valid, but abcd is not.
  auto shared_diagnostics = histogram_set.mutable_shared_diagnostics();
  proto::Diagnostic stories_diag;
  generic_set = stories_diag.mutable_generic_set();
  generic_set->add_values("\"browse:news:cnn\"");
  (*shared_diagnostics)["923e4567-e89b-12d3-a456-426655440000"] = stories_diag;

  proto::Diagnostic masters_diag;
  generic_set = masters_diag.mutable_generic_set();
  generic_set->add_values("\"WebRTCPerf\"");
  (*shared_diagnostics)["04399b74-913d-4afa-b464-d8a43f7729ad"] = masters_diag;

  proto::Diagnostic bots_diag;
  generic_set = bots_diag.mutable_generic_set();
  generic_set->add_values("\"webrtc-linux-large-tests\"");
  (*shared_diagnostics)["f7f17394-fa4a-481e-86bd-a82cd55935a7"] = bots_diag;

  proto::Diagnostic benchmarks_diag;
  generic_set = benchmarks_diag.mutable_generic_set();
  generic_set->add_values("\"webrtc_perf_tests\"");
  (*shared_diagnostics)["5e416298-e572-463d-9a3d-5f881d1cb200"] =
      benchmarks_diag;

  proto::Diagnostic point_id_diag;
  generic_set = point_id_diag.mutable_generic_set();
  generic_set->add_values("123456");
  (*shared_diagnostics)["88ea36c7-6dcb-4ba8-ba56-1979de05e16f"] = point_id_diag;

  printf("%s\n", histogram_set.DebugString().c_str());
}

}  // namespace catapult

int main(int argc, char** argv) {
  catapult::ExampleProtoToJson();
  return 0;
}
