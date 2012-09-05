#!/bin/sh
BASEDIR=$(dirname $0)
SERVERPATH=$BASEDIR/stream_server/standalone.py
SERVERROOT=$BASEDIR/../
HANDLERSPATH=examples/stream_server/handlers
echo Navigate to http://localhost:8001/examples/stream_trace_viewer.html
python $SERVERPATH -d $SERVERROOT -w $HANDLERSPATH -p 8001
