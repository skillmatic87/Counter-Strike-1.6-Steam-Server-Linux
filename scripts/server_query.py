"""Bounded A2S_INFO query and parser for current GoldSrc servers."""
import socket
import struct

REQUEST = b'\xff\xff\xff\xffTSource Engine Query\0'


def parse_info(packet):
    if not packet.startswith(b'\xff\xff\xff\xffI') or len(packet) < 6:
        raise ValueError('Not an A2S_INFO response.')
    offset = 6  # response type and protocol version
    strings = []
    for _ in range(4):
        end = packet.find(b'\0', offset)
        if end < 0:
            raise ValueError('Truncated A2S_INFO string.')
        strings.append(packet[offset:end].decode('utf-8', 'replace'))
        offset = end + 1
    if len(packet) < offset + 9:
        raise ValueError('Truncated A2S_INFO counts.')
    app_id, players, slots, bots = struct.unpack_from('<HBBB', packet, offset)
    if strings[2] != 'cstrike' or slots > 32 or players > slots:
        raise ValueError('Unexpected Counter-Strike server response.')
    return dict(name=strings[0], map=strings[1], players=players, maxPlayers=slots,
                bots=bots, protocol=packet[5], appId=app_id,
                password=bool(packet[offset + 7]), vac=bool(packet[offset + 8]))


def query_info(endpoint, timeout=.5):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        udp.settimeout(timeout)
        udp.connect(endpoint)
        udp.send(REQUEST)
        packet = udp.recv(65507)
        if packet.startswith(b'\xff\xff\xff\xffA'):
            if len(packet) != 9:
                raise ValueError('Invalid A2S challenge.')
            udp.send(REQUEST + packet[5:9])
            packet = udp.recv(65507)
        return parse_info(packet)


if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address', nargs='?', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=27015)
    args = parser.parse_args()
    try:
        print(json.dumps(query_info((args.address, args.port), 3), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Server query failed: {error}\n')
