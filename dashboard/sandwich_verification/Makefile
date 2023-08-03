generate_pb_grpc:
	python3 -m grpc_tools.protoc \
	-I ../../../skia/buildbot/cabe/go/proto/ \
	--python_out=./cabe_grpc \
	--grpc_python_out=./cabe_grpc \
	../../../skia/buildbot/cabe/go/proto/service.proto

generate_pb:
	python3 -m grpc_tools.protoc \
	-I ../../../skia/buildbot/cabe/go/proto/ \
	--python_out=./cabe_grpc \
	../../../skia/buildbot/cabe/go/proto/analysis.proto \
	../../../skia/buildbot/cabe/go/proto/spec.proto

generate: generate_pb generate_pb_grpc
