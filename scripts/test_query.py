import socket
import struct
import threading
import unittest

from server_query import parse_info, query_info, REQUEST


def response():
    return b'\xff\xff\xff\xffI\x30Fixture\0de_dust2\0cstrike\0Counter-Strike\0'+struct.pack('<HBBBccBB',10,2,32,1,b'd',b'l',0,1)+b'1.1.2.7/Stdio\0'


class QueryTests(unittest.TestCase):
    def test_valid_reply_and_short_packets(self):
        parsed=parse_info(response())
        self.assertEqual((parsed['players'],parsed['maxPlayers'],parsed['vac']),(2,32,True))
        for end in range(len(response())-len(b'1.1.2.7/Stdio\0')):
            with self.subTest(end=end), self.assertRaises(ValueError):parse_info(response()[:end])

    def test_challenge_exchange(self):
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
            server.bind(('127.0.0.1',0));server.settimeout(2)
            errors=[]
            def answer():
                try:
                    first,peer=server.recvfrom(4096);self.assertEqual(first,REQUEST)
                    server.sendto(b'\xff\xff\xff\xffAabcd',peer)
                    second,peer=server.recvfrom(4096);self.assertEqual(second,REQUEST+b'abcd')
                    server.sendto(response(),peer)
                except Exception as error:errors.append(error)
            thread=threading.Thread(target=answer);thread.start()
            self.assertEqual(query_info(server.getsockname(),1)['name'],'Fixture')
            thread.join();self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
