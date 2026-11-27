"""Read Windows PE imports without requiring external developer tools."""
from pathlib import Path
import struct


def imports(path):
    data=Path(path).read_bytes()
    if data[:2]!=b"MZ":return set()
    pe=struct.unpack_from("<I",data,0x3c)[0]
    if data[pe:pe+4]!=b"PE\0\0":return set()
    count=struct.unpack_from("<H",data,pe+6)[0]
    optional=pe+24
    size=struct.unpack_from("<H",data,pe+20)[0]
    magic=struct.unpack_from("<H",data,optional)[0]
    directory=optional+(112 if magic==0x20b else 96)
    base=struct.unpack_from("<Q" if magic==0x20b else "<I",data,optional+(24 if magic==0x20b else 28))[0]
    sections=[]
    for i in range(count):
        pos=optional+size+i*40
        virtual_size,virtual,raw_size,raw=struct.unpack_from("<IIII",data,pos+8)
        sections.append((virtual,max(virtual_size,raw_size),raw))
    def offset(rva):
        for address,length,raw in sections:
            if address<=rva<address+length:return raw+rva-address
        return rva
    def name(rva):
        start=offset(rva);end=data.find(b"\0",start)
        return data[start:end].decode("ascii").lower()
    result=set()
    for index,stride,name_offset in [(1,20,12),(13,32,4)]:
        rva,length=struct.unpack_from("<II",data,directory+index*8)
        if not rva:continue
        pos=offset(rva)
        while any(data[pos:pos+stride]):
            entry=struct.unpack_from("<I",data,pos+name_offset)[0]
            if index==13 and not struct.unpack_from("<I",data,pos)[0]&1:entry-=base
            if entry:result.add(name(entry))
            pos+=stride
    return result
