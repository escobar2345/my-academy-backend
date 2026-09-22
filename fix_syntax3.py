#!/usr/bin/env python
"""Fix the closing of the try block in send_admin_daily_report."""

with open('app/boi-rsu/boirsu.py', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Fix: Line 2052 should have 8 spaces (still inside try)
#      Line 2054 should have 8 spaces (still inside try)
#      After 2054, add the except clause

fixed = []
for i, line in enumerate(lines, 1):
    if i == 2052:
        # Closing paren should be indented 8 spaces (still in try block)
        fixed.append('        )\n')
    elif i == 2054:
        # send_whatsapp_admin should be indented 8 spaces (still in try block)
        fixed.append('        send_whatsapp_admin(report)\n')
    elif i == 2055:
        # After send_whatsapp_admin, add the except clause
        fixed.append('    except Exception as e:\n')
        fixed.append('        print(f"[ERROR] Failed to send admin daily report: {e}")\n')
        fixed.append(line)  # Keep the blank line after
    else:
        fixed.append(line)

with open('app/boi-rsu/boirsu.py', 'w', encoding='utf-8-sig') as f:
    f.writelines(fixed)

print("[OK] Fixed try/except block closure")
