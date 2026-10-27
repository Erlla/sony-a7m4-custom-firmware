"""Remove the Off-page RAM diagnostics entry from the exact LUT AP component.

The AArch64 branch skips the diagnostic activation block and continues with
normal key dispatch. It preserves component size, addresses and all other bytes.
This tool patches a local appFw.so component; it does not build or flash firmware.
"""
from pathlib import Path
import argparse
import hashlib
import struct

SOURCE_SHA256='6b32c13e1b51b426ba4a29bd0f5073b242abaceaacf82a5aeab3fe9719486293'
OUTPUT_SHA256='cda216ccbbf3ad628a4a3b1c4d282d82ce36de9dd37e644f5f29336087e12aed'
VA=0x903ec48
OFFSET=0x5e8ec48
ORIGINAL=bytes.fromhex('01eeff54')
REPLACEMENT=bytes.fromhex('70ffff17')


def patch(data):
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Unsupported AP input; exact source SHA-256 required')
    if data[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',data,18)[0]!=183:
        raise ValueError('Expected little-endian AArch64 ELF64')
    phoff=struct.unpack_from('<Q',data,32)[0]
    entsize,count=struct.unpack_from('<HH',data,54)
    matches=[]
    for i in range(count):
        kind,flags,off,va,_,size,_,_=struct.unpack_from('<IIQQQQQQ',data,phoff+i*entsize)
        if kind==1 and flags&1 and va<=VA and VA+4<=va+size:
            matches.append(off+VA-va)
    if matches!=[OFFSET] or data[OFFSET:OFFSET+4]!=ORIGINAL:
        raise ValueError('ELF mapping or branch differs')
    result=bytearray(data)
    result[OFFSET:OFFSET+4]=REPLACEMENT
    result=bytes(result)
    if hashlib.sha256(result).hexdigest()!=OUTPUT_SHA256:
        raise ValueError('Output identity differs')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    result=patch(args.input.read_bytes())
    with args.output.open('xb') as f:
        f.write(result)
    print(OUTPUT_SHA256)


if __name__=='__main__':
    main()
