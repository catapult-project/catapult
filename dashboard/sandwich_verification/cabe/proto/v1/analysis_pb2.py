# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: cabe/proto/v1/analysis.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from cabe.proto.v1 import spec_pb2 as cabe_dot_proto_dot_v1_dot_spec__pb2


DESCRIPTOR = _descriptor.FileDescriptor(
  name='cabe/proto/v1/analysis.proto',
  package='cabe.v1',
  syntax='proto3',
  serialized_pb=_b('\n\x1c\x63\x61\x62\x65/proto/v1/analysis.proto\x12\x07\x63\x61\x62\x65.v1\x1a\x18\x63\x61\x62\x65/proto/v1/spec.proto\"X\n\x10\x41nalysisMetadata\x12\x11\n\treport_id\x18\x01 \x01(\t\x12\x31\n\x0b\x64iagnostics\x18\x02 \x01(\x0b\x32\x1c.cabe.v1.AnalysisDiagnostics\"\x8b\x02\n\x13\x41nalysisDiagnostics\x12\x41\n\x17\x65xcluded_swarming_tasks\x18\x01 \x03(\x0b\x32 .cabe.v1.SwarmingTaskDiagnostics\x12\x36\n\x11\x65xcluded_replicas\x18\x02 \x03(\x0b\x32\x1b.cabe.v1.ReplicaDiagnostics\x12\x41\n\x17included_swarming_tasks\x18\x03 \x03(\x0b\x32 .cabe.v1.SwarmingTaskDiagnostics\x12\x36\n\x11included_replicas\x18\x04 \x03(\x0b\x32\x1b.cabe.v1.ReplicaDiagnostics\"2\n\x0eSwarmingTaskId\x12\x0f\n\x07task_id\x18\x01 \x01(\t\x12\x0f\n\x07project\x18\x02 \x01(\t\"O\n\x17SwarmingTaskDiagnostics\x12#\n\x02id\x18\x01 \x01(\x0b\x32\x17.cabe.v1.SwarmingTaskId\x12\x0f\n\x07message\x18\x02 \x03(\t\"\x9d\x01\n\x12ReplicaDiagnostics\x12\x16\n\x0ereplica_number\x18\x01 \x01(\x05\x12-\n\x0c\x63ontrol_task\x18\x02 \x01(\x0b\x32\x17.cabe.v1.SwarmingTaskId\x12/\n\x0etreatment_task\x18\x03 \x01(\x0b\x32\x17.cabe.v1.SwarmingTaskId\x12\x0f\n\x07message\x18\x04 \x03(\t\"\xb2\x01\n\x0e\x41nalysisResult\x12\x11\n\tresult_id\x18\x01 \x01(\t\x12\x30\n\x0f\x65xperiment_spec\x18\x02 \x01(\x0b\x32\x17.cabe.v1.ExperimentSpec\x12\x34\n\x11\x61nalysis_metadata\x18\x03 \x01(\x0b\x32\x19.cabe.v1.AnalysisMetadata\x12%\n\tstatistic\x18\x04 \x01(\x0b\x32\x12.cabe.v1.Statistic\"\xa0\x01\n\tStatistic\x12\r\n\x05lower\x18\x01 \x01(\x01\x12\r\n\x05upper\x18\x02 \x01(\x01\x12\x0f\n\x07p_value\x18\x03 \x01(\x01\x12\x1a\n\x12significance_level\x18\x04 \x01(\x01\x12\x16\n\x0epoint_estimate\x18\x06 \x01(\x01\x12\x16\n\x0e\x63ontrol_median\x18\x07 \x01(\x01\x12\x18\n\x10treatment_median\x18\x08 \x01(\x01\x42!Z\x1fgo.skia.org/infra/cabe/go/protob\x06proto3')
  ,
  dependencies=[cabe_dot_proto_dot_v1_dot_spec__pb2.DESCRIPTOR,])




_ANALYSISMETADATA = _descriptor.Descriptor(
  name='AnalysisMetadata',
  full_name='cabe.v1.AnalysisMetadata',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='report_id', full_name='cabe.v1.AnalysisMetadata.report_id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='diagnostics', full_name='cabe.v1.AnalysisMetadata.diagnostics', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=67,
  serialized_end=155,
)


_ANALYSISDIAGNOSTICS = _descriptor.Descriptor(
  name='AnalysisDiagnostics',
  full_name='cabe.v1.AnalysisDiagnostics',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='excluded_swarming_tasks', full_name='cabe.v1.AnalysisDiagnostics.excluded_swarming_tasks', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='excluded_replicas', full_name='cabe.v1.AnalysisDiagnostics.excluded_replicas', index=1,
      number=2, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='included_swarming_tasks', full_name='cabe.v1.AnalysisDiagnostics.included_swarming_tasks', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='included_replicas', full_name='cabe.v1.AnalysisDiagnostics.included_replicas', index=3,
      number=4, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=158,
  serialized_end=425,
)


_SWARMINGTASKID = _descriptor.Descriptor(
  name='SwarmingTaskId',
  full_name='cabe.v1.SwarmingTaskId',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='task_id', full_name='cabe.v1.SwarmingTaskId.task_id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='project', full_name='cabe.v1.SwarmingTaskId.project', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=427,
  serialized_end=477,
)


_SWARMINGTASKDIAGNOSTICS = _descriptor.Descriptor(
  name='SwarmingTaskDiagnostics',
  full_name='cabe.v1.SwarmingTaskDiagnostics',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='cabe.v1.SwarmingTaskDiagnostics.id', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='message', full_name='cabe.v1.SwarmingTaskDiagnostics.message', index=1,
      number=2, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=479,
  serialized_end=558,
)


_REPLICADIAGNOSTICS = _descriptor.Descriptor(
  name='ReplicaDiagnostics',
  full_name='cabe.v1.ReplicaDiagnostics',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='replica_number', full_name='cabe.v1.ReplicaDiagnostics.replica_number', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='control_task', full_name='cabe.v1.ReplicaDiagnostics.control_task', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='treatment_task', full_name='cabe.v1.ReplicaDiagnostics.treatment_task', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='message', full_name='cabe.v1.ReplicaDiagnostics.message', index=3,
      number=4, type=9, cpp_type=9, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=561,
  serialized_end=718,
)


_ANALYSISRESULT = _descriptor.Descriptor(
  name='AnalysisResult',
  full_name='cabe.v1.AnalysisResult',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='result_id', full_name='cabe.v1.AnalysisResult.result_id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='experiment_spec', full_name='cabe.v1.AnalysisResult.experiment_spec', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='analysis_metadata', full_name='cabe.v1.AnalysisResult.analysis_metadata', index=2,
      number=3, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='statistic', full_name='cabe.v1.AnalysisResult.statistic', index=3,
      number=4, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=721,
  serialized_end=899,
)


_STATISTIC = _descriptor.Descriptor(
  name='Statistic',
  full_name='cabe.v1.Statistic',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='lower', full_name='cabe.v1.Statistic.lower', index=0,
      number=1, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='upper', full_name='cabe.v1.Statistic.upper', index=1,
      number=2, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='p_value', full_name='cabe.v1.Statistic.p_value', index=2,
      number=3, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='significance_level', full_name='cabe.v1.Statistic.significance_level', index=3,
      number=4, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='point_estimate', full_name='cabe.v1.Statistic.point_estimate', index=4,
      number=6, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='control_median', full_name='cabe.v1.Statistic.control_median', index=5,
      number=7, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='treatment_median', full_name='cabe.v1.Statistic.treatment_median', index=6,
      number=8, type=1, cpp_type=5, label=1,
      has_default_value=False, default_value=float(0),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=902,
  serialized_end=1062,
)

_ANALYSISMETADATA.fields_by_name['diagnostics'].message_type = _ANALYSISDIAGNOSTICS
_ANALYSISDIAGNOSTICS.fields_by_name['excluded_swarming_tasks'].message_type = _SWARMINGTASKDIAGNOSTICS
_ANALYSISDIAGNOSTICS.fields_by_name['excluded_replicas'].message_type = _REPLICADIAGNOSTICS
_ANALYSISDIAGNOSTICS.fields_by_name['included_swarming_tasks'].message_type = _SWARMINGTASKDIAGNOSTICS
_ANALYSISDIAGNOSTICS.fields_by_name['included_replicas'].message_type = _REPLICADIAGNOSTICS
_SWARMINGTASKDIAGNOSTICS.fields_by_name['id'].message_type = _SWARMINGTASKID
_REPLICADIAGNOSTICS.fields_by_name['control_task'].message_type = _SWARMINGTASKID
_REPLICADIAGNOSTICS.fields_by_name['treatment_task'].message_type = _SWARMINGTASKID
_ANALYSISRESULT.fields_by_name['experiment_spec'].message_type = cabe_dot_proto_dot_v1_dot_spec__pb2._EXPERIMENTSPEC
_ANALYSISRESULT.fields_by_name['analysis_metadata'].message_type = _ANALYSISMETADATA
_ANALYSISRESULT.fields_by_name['statistic'].message_type = _STATISTIC
DESCRIPTOR.message_types_by_name['AnalysisMetadata'] = _ANALYSISMETADATA
DESCRIPTOR.message_types_by_name['AnalysisDiagnostics'] = _ANALYSISDIAGNOSTICS
DESCRIPTOR.message_types_by_name['SwarmingTaskId'] = _SWARMINGTASKID
DESCRIPTOR.message_types_by_name['SwarmingTaskDiagnostics'] = _SWARMINGTASKDIAGNOSTICS
DESCRIPTOR.message_types_by_name['ReplicaDiagnostics'] = _REPLICADIAGNOSTICS
DESCRIPTOR.message_types_by_name['AnalysisResult'] = _ANALYSISRESULT
DESCRIPTOR.message_types_by_name['Statistic'] = _STATISTIC
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

AnalysisMetadata = _reflection.GeneratedProtocolMessageType('AnalysisMetadata', (_message.Message,), dict(
  DESCRIPTOR = _ANALYSISMETADATA,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.AnalysisMetadata)
  ))
_sym_db.RegisterMessage(AnalysisMetadata)

AnalysisDiagnostics = _reflection.GeneratedProtocolMessageType('AnalysisDiagnostics', (_message.Message,), dict(
  DESCRIPTOR = _ANALYSISDIAGNOSTICS,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.AnalysisDiagnostics)
  ))
_sym_db.RegisterMessage(AnalysisDiagnostics)

SwarmingTaskId = _reflection.GeneratedProtocolMessageType('SwarmingTaskId', (_message.Message,), dict(
  DESCRIPTOR = _SWARMINGTASKID,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.SwarmingTaskId)
  ))
_sym_db.RegisterMessage(SwarmingTaskId)

SwarmingTaskDiagnostics = _reflection.GeneratedProtocolMessageType('SwarmingTaskDiagnostics', (_message.Message,), dict(
  DESCRIPTOR = _SWARMINGTASKDIAGNOSTICS,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.SwarmingTaskDiagnostics)
  ))
_sym_db.RegisterMessage(SwarmingTaskDiagnostics)

ReplicaDiagnostics = _reflection.GeneratedProtocolMessageType('ReplicaDiagnostics', (_message.Message,), dict(
  DESCRIPTOR = _REPLICADIAGNOSTICS,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.ReplicaDiagnostics)
  ))
_sym_db.RegisterMessage(ReplicaDiagnostics)

AnalysisResult = _reflection.GeneratedProtocolMessageType('AnalysisResult', (_message.Message,), dict(
  DESCRIPTOR = _ANALYSISRESULT,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.AnalysisResult)
  ))
_sym_db.RegisterMessage(AnalysisResult)

Statistic = _reflection.GeneratedProtocolMessageType('Statistic', (_message.Message,), dict(
  DESCRIPTOR = _STATISTIC,
  __module__ = 'cabe.proto.v1.analysis_pb2'
  # @@protoc_insertion_point(class_scope:cabe.v1.Statistic)
  ))
_sym_db.RegisterMessage(Statistic)


DESCRIPTOR.has_options = True
DESCRIPTOR._options = _descriptor._ParseOptions(descriptor_pb2.FileOptions(), _b('Z\037go.skia.org/infra/cabe/go/proto'))
# @@protoc_insertion_point(module_scope)
