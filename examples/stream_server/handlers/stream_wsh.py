import time

def web_socket_do_extra_handshake(request):
    # This example handler accepts any request. See origin_check_wsh.py for how
    # to reject access from untrusted scripts based on origin value.

    pass  # Always accept.

def make_slice(start_time, elapsed_time, label, last):
    out = []
    out.append("{")
    out.append('\"l\": \"{0}\",'.format(label))
    out.append('\"s\": {0},'.format(start_time))
    out.append('\"e\": {0}'.format(start_time+elapsed_time))
    out.append('}')
    if last == False:
        out.append(',')
    return ''.join(out)

def make_thread(thread_name, base_time):
    out = []
    out.append('\"n\": \"{0}\",'.format(thread_name))
    out.append('\"s\": [')
    out.append(make_slice(base_time, 4, "alligator", False))
    out.append(make_slice(base_time+2, 1, "bandicoot", False))
    out.append(make_slice(base_time+5, 1, "cheetah", True))
    out.append(']')
    return ''.join(out)

def make_thread_payload(pid, thread_name, base_time):
    out = []
    out.append('\"pid\": \"{0}\",'.format(pid))
    out.append('\"td\": {')
    out.append(make_thread(thread_name, base_time))
    out.append('}')
    return ''.join(out)

def make_thread_command(base_time, thread_name):
    out = []
    out.append('{ \"cmd\": \"ptd\",')
    out.append(make_thread_payload('314159', thread_name,  base_time))
    out.append('}')
    return ''.join(out)

def make_count(start_time, count, bytes, last):
    out = []
    out.append('{')
    out.append('\"t\": {0},'.format(start_time))
    out.append('\"c\": {0},'.format(count))
    out.append('\"b\": {0}'.format(bytes))
    out.append('}')
    if last == False:
        out.append(',')
    return ''.join(out)

def make_allocator(allocator_name, base_time):
    out = []
    out.append('\"n\": \"{0}\",'.format(allocator_name))
    out.append('\"c\": [')
    out.append(make_count(base_time, 1, 16, False))
    out.append(make_count(base_time+1, 2, 32, False))
    out.append(make_count(base_time+2, 3, 48, False))
    out.append(make_count(base_time+3, 4, 64, False))
    out.append(make_count(base_time+8, 1, 16, True))
    out.append(']')
    return ''.join(out)

def make_allocator_payload(pid, allocator_name, base_time):
    out = []
    out.append('\"pid\": \"{0}\",'.format(pid))
    out.append('\"ad\": {')
    out.append(make_allocator(allocator_name, base_time))
    out.append('}')
    return ''.join(out)

def make_allocator_command(base_time, allocator_name):
    out = []
    out.append('{ \"cmd\": \"pad\",')
    out.append(make_allocator_payload('314159', allocator_name, base_time))
    out.append('}')
    return ''.join(out)

def web_socket_transfer_data(request):
    start_time = 0;
    while True:
        msg = make_thread_command(start_time, 'apple')
        request.ws_stream.send_message(msg, binary=False)
        msg = make_thread_command(start_time+1, 'banana')
        request.ws_stream.send_message(msg, binary=False)
        msg = make_thread_command(start_time+2, 'cherry')
        request.ws_stream.send_message(msg, binary=False)
        msg = make_allocator_command(start_time+2, 'Base')
        request.ws_stream.send_message(msg, binary=False)
        msg = make_allocator_command(start_time+3, 'Font')
        request.ws_stream.send_message(msg, binary=False)
        msg = make_allocator_command(start_time+5, 'Textures')
        request.ws_stream.send_message(msg, binary=False)
        start_time += 16
        time.sleep(0.16)

# vi:sts=4 sw=4 et
