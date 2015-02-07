import asyncio
import logging

from mysqlproto.protocol import start_mysql_server
from mysqlproto.protocol.base import OK, ERR, EOF
from mysqlproto.protocol.flags import Capability
from mysqlproto.protocol.handshake import HandshakeV10, HandshakeResponse41, AuthSwitchRequest
from mysqlproto.protocol.query import ColumnDefinition, ColumnDefinitionList, ResultSet


@asyncio.coroutine
def accept_server(server_reader, server_writer):
    task = asyncio.Task(handle_server(server_reader, server_writer))


@asyncio.coroutine
def handle_server(server_reader, server_writer):
    seq = 0

    handshake = HandshakeV10()
    handshake.write(server_writer, seq)
    seq += 1
    yield from server_writer.drain()

    handshake_response = yield from HandshakeResponse41.read(server_reader.packet(seq), handshake.capability)
    seq += 1
    print("<=", handshake_response.__dict__)

    capability = handshake_response.capability_effective

    if (Capability.PLUGIN_AUTH in capability and
            handshake.auth_plugin != handshake_response.auth_plugin):
        AuthSwitchRequest().write(server_writer, seq)
        seq += 1
        yield from server_writer.drain()

        auth_response = yield from server_reader.packet(seq).read()
        seq += 1
        print("<=", auth_response)

    result = OK(capability, handshake.status)
    result.write(server_writer, seq)
    yield from server_writer.drain()

    while True:
        seq = 0

        packet = server_reader.packet(seq)
        seq += 1
        cmd = (yield from packet.read(1))[0]
        print("<=", cmd)

        if cmd == 1:
            return

        elif cmd == 3:
            query = (yield from packet.read()).decode('ascii')
            print("<=   query:", query)

            if query == 'select 1':
                ColumnDefinitionList((ColumnDefinition('database'),)).write(server_writer, 1)
                EOF(capability, handshake.status).write(server_writer)
                ResultSet(('test',)).write(server_writer)
                result = EOF(capability, handshake.status)
                seq = None
            else:
                result = OK(capability, handshake.status)

        else:
            result = ERR(capability)

        result.write(server_writer, seq)
        yield from server_writer.drain()


logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
f = start_mysql_server(handle_server, host=None, port=3306)
loop.run_until_complete(f)
loop.run_forever()
