#!/usr/bin/env python
with open('app/boi-rsu/boirsu.py', 'rb') as f:
    lines = f.readlines()
    for i in range(2008, min(2035, len(lines))):
        line = lines[i].decode('utf-8-sig', errors='replace').rstrip()
        print(f'{i+1:4}: {repr(line)}')
