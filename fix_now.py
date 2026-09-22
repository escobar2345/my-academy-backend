with open('app/boi-rsu/boirsu.py', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

fixed = []
for i, line in enumerate(lines, 1):
    if i in (2049, 2050, 2051):
        fixed.append('        ' + line.lstrip())
    elif i == 2052:
        fixed.append('        )\n')
    elif i == 2054:
        fixed.append('        send_whatsapp_admin(report)\n')
    elif i == 2055:
        fixed.append('    except Exception as e:\n')
        fixed.append('        print(f"[ERROR] Failed to send admin daily report: {e}")\n')
        fixed.append(line)
    else:
        fixed.append(line)

with open('app/boi-rsu/boirsu.py', 'w', encoding='utf-8-sig') as f:
    f.writelines(fixed)

print('[OK] Fixed all indentation')
