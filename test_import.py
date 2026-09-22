#!/usr/bin/env python
from app.boi_rsu import load_module

try:
    m = load_module()
    print(f'[YES] BOI RSU module loaded successfully')
    
    # List some functions
    funcs = [x for x in dir(m) if not x.startswith('_') and callable(getattr(m, x))]
    print(f'[YES] Available functions ({len(funcs)}): {", ".join(funcs[:8])}')
    
except Exception as e:
    print(f'[ERROR] Failed to load BOI RSU: {e}')
    import traceback
    traceback.print_exc()
