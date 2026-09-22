#!/usr/bin/env python
"""Fix the indentation errors in send_admin_daily_report."""

with open('app/boi-rsu/boirsu.py', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Fix all the indentation issues in the send_admin_daily_report function
# Lines 2030-2031 (inside for loop) need 12 spaces, not 8
# Lines 2044-2046 (inside for loop) need 12 spaces, not 8

fixed = []
for i, line in enumerate(lines, 1):
    if i == 2030:
        # Inside for loop - needs 12 spaces
        fixed.append('            path = s.get("career_path", "unknown")\n')
    elif i == 2031:
        # Inside for loop - needs 12 spaces
        fixed.append('            paths[path] = paths.get(path, 0) + 1\n')
    elif i == 2044:
        # Inside for loop - needs 12 spaces
        fixed.append('            roadmap = CAREER_ROADMAPS.get(path, {})\n')
    elif i == 2045:
        # Inside for loop - needs 12 spaces
        fixed.append('            title = roadmap.get("title", path)\n')
    elif i == 2046:
        # Inside for loop - needs 12 spaces
        fixed.append('            report += f"- {title}: {count} students\\n"\n')
    else:
        fixed.append(line)

with open('app/boi-rsu/boirsu.py', 'w', encoding='utf-8-sig') as f:
    f.writelines(fixed)

print("[OK] Fixed nested loop indentation")
