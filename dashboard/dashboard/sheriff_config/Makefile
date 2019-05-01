PROTOC=protoc

proto/sheriff_pb2.py: ../proto/sheriff.proto
	mkdir -p proto && \
		touch proto/__init__.py && \
		$(PROTOC) -I../proto --python_out=proto ../proto/sheriff.proto

.PHONY: clean

all: proto/sheriff_pb2.py

clean:
	rm -f proto/*
