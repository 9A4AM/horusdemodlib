#!/usr/bin/env python3
#
#   HorusDemodLib - Encoder helper functions
#
import ctypes
from ctypes import *
import codecs
import logging
import sys
from enum import Enum
import os
import logging
from .decoder import decode_packet, hex_to_bytes

PACKET_MAX_SIZE = 1024


class Encoder():
    """
    HorusLib provides a binding to horuslib to demoulate frames.

    Example usage:

    from horuslib import HorusLib, Mode
    with HorusLib(, mode=Mode.BINARY, verbose=False) as horus:
        with open("test.wav", "rb") as f:
            while True:
                data = f.read(horus.nin*2)
                if horus.nin != 0 and data == b'': #detect end of file
                    break
                output = horus.demodulate(data)
                if output.crc_pass and output.data:
                    print(f'{output.data.hex()} SNR: {output.snr}')
                    for x in range(horus.mfsk):
                        print(f'F{str(x)}: {float(output.extended_stats.f_est[x])}')

    """

    def __init__(
        self,
        libpath=f"",
    ):
        """
        Parameters
        ----------
        libpath : str
            Path to libhorus
        """

        if sys.platform == "darwin":
            libpath = os.path.join(libpath, "libhorus.dylib")
        elif sys.platform == "win32":
            libpath = os.path.join(libpath, "libhorus.dll")
        else:
            libpath = os.path.join(libpath, "libhorus.so")

        # future improvement would be to try a few places / names
        self.c_lib = ctypes.cdll.LoadLibrary(libpath)


        # Encoder/decoder functions
        self.c_lib.horus_l2_get_num_tx_data_bytes.restype = c_int

        self.c_lib.horus_l2_encode_tx_packet.restype = c_int
        # self.c_lib.horus_l2_encode_tx_packet.argtype = [
        #     POINTER(c_ubyte),
        #     c_ubyte * 
        #     POINTER(c_ubyte),
        #     c_int
        # ]

        self.c_lib.horus_l2_decode_rx_packet.argtype = [
            POINTER(c_ubyte),
            POINTER(c_ubyte),
            c_int
        ]

        self.c_lib.horus_l2_gen_crc16.restype = c_ushort
        self.c_lib.horus_l2_gen_crc16.argtype = [
            POINTER(c_ubyte),
            c_uint8
        ]

        # Init 
        self.c_lib.horus_l2_init()

    # in case someone wanted to use `with` style. I'm not sure if closing the modem does a lot.
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self) -> None:
        """
        Closes Horus modem. Does nothing here.
        """
        pass

    def get_num_tx_data_bytes(self, packet_size) -> int:
        """
        Calculate the number of transmit data bytes (uw+packet+fec) for a given
        input packet size.
        """
        return int(self.c_lib.horus_l2_get_num_tx_data_bytes(int(packet_size)))


    def horus_l2_encode_packet(self, packet):
        """
        Encode a packet using the Horus Binary FEC scheme, which:
        - Generates Golay (23,12) FEC for the packet
        - Adds this onto the packet contents, and interleaves/scrambles
        - Adds a unique word (0x2424) to the start.

        Packet input must be provided as bytes.
        """

        if type(packet) != bytes:
            raise TypeError("Input to encode_packet must be bytes!")

        _unencoded = c_ubyte * len(packet)
        _unencoded = _unencoded.from_buffer_copy(packet)
        _num_encoded_bytes = self.get_num_tx_data_bytes(len(packet))
        _encoded = c_ubyte * _num_encoded_bytes
        _encoded = _encoded()

        self.c_lib.horus_l2_encode_tx_packet.argtype = [
            c_ubyte * _num_encoded_bytes,
            c_ubyte * len(packet),
            c_int
        ]

        _num_bytes = int(self.c_lib.horus_l2_encode_tx_packet(_encoded, _unencoded, int(len(packet))))

        return (bytes(_encoded), _num_bytes)


    def horus_l2_decode_packet(self, packet, num_payload_bytes):
        """
        Decode a Horus-Binary encoded data packet.

        The packet must be provided as bytes, and must have the 2-byte unique word (0x2424)
        at the start.

        The expected number of output bytes must also be provided (22 or 32 for Horus v1 / v2 respectively)
        """

        if type(packet) != bytes:
            raise TypeError("Input to encode_packet must be bytes!")
        _encoded = c_ubyte * len(packet)
        _encoded = _encoded.from_buffer_copy(packet)
        _decoded = c_ubyte * num_payload_bytes
        _decoded = _decoded()

        self.c_lib.horus_l2_encode_tx_packet.argtype = [
            c_ubyte * num_payload_bytes,
            c_ubyte * len(packet),
            c_int
        ]

        self.c_lib.horus_l2_decode_rx_packet(_decoded, _encoded, num_payload_bytes)

        return bytes(_decoded)


if __name__ == "__main__":
    import sys

    e = Encoder()

    # Check of get_num_tx_data_bytes
    print(f"Horus v1: 22 bytes in, {e.get_num_tx_data_bytes(22)} bytes out.")
    print(f"Horus v2: 32 bytes in, {e.get_num_tx_data_bytes(32)} bytes out.")

    print("Encoder Tests: ")
    horus_v1_unencoded = "000900071E2A000000000000000000000000259A6B14"
    print(f"  Horus v1 Input:  {horus_v1_unencoded}")
    horus_v1_unencoded_bytes = codecs.decode(horus_v1_unencoded, 'hex')
    (_encoded, _num_bytes) = e.horus_l2_encode_packet(horus_v1_unencoded_bytes)
    print(f"  Horus v1 Output: {codecs.encode(_encoded, 'hex').decode().upper()}")


    print("Decoder Tests:")
    horus_v1_encoded = "2424C06B300D0415C5DBD332EFD7C190D7AF7F3C2891DE9F4BA1EB2B437BE1E2D8419D3DC9E44FDF78DAA07A98"
    print(f"  Horus v1 Input:  {horus_v1_encoded}")
    horus_v1_encoded_bytes = codecs.decode(horus_v1_encoded, 'hex')
    _decoded = e.horus_l2_decode_packet(horus_v1_encoded_bytes, 22)
    print(f"  Horus v1 Output: {codecs.encode(_decoded, 'hex').decode().upper()}")

