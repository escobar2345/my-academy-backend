#!/usr/bin/env python
"""Fix the syntax error in send_admin_daily_report."""

with open('app/boi-rsu/boirsu.py', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Fix line 2018: indent it properly to be inside the try block
# Change from 4 spaces to 8 spaces
fixed = []
for i, line in enumerate(lines, 1):
    if i == 2018:
        # 'now = datetime.now()' needs 8 spaces, not 4
        fixed.append('        now = datetime.now()\n')
    elif i == 2019:
        # 'today = date.today().isoformat()' needs 8 spaces, not 4
        fixed.append('        today = date.today().isoformat()\n')
    elif 2020 <= i <= 2048:
        # All lines in the try block body need 8 spaces instead of 4
        if line.startswith('    ') and not line.startswith('        '):
            # Add 4 more spaces
            fixed.append('    ' + line)
        elif i == 2048:
            # After the send_whatsapp_admin call, add the except clause
            if 'send_whatsapp_admin(report)' in line:
                fixed.append(line)
                fixed.append('    except Exception as e:\n')
                fixed.append('        print(f"[ERROR] Failed to send admin daily report: {e}")\n')
            else:
                fixed.append(line)
        else:
            fixed.append(line)
    else:
        fixed.append(line)

with open('app/boi-rsu/boirsu.py', 'w', encoding='utf-8-sig') as f:
    f.writelines(fixed)

print("[OK] Fixed send_admin_daily_report indentation and added except clause")
