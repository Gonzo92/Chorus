import subprocess
import json
import re

def adb(cmd):
    r = subprocess.run(f'adb shell {cmd}', capture_output=True, text=True, timeout=10)
    return r.stdout.strip(), r.stderr.strip()

print('='*60)
print('IMMS/VoLTE INVESTIGATION - S24 Ultra')
print('='*60)

# 1. settings secure
print('\n[1] settings secure (ims/volte/voip)')
out, _ = adb('settings list secure')
for line in out.split('\n'):
    if any(k in line.lower() for k in ['ims', 'volte', 'voip', 'mmtel', 'sip']):
        print(f'  FOUND: {line}')
if not any('ims' in l.lower() or 'volte' in l.lower() or 'voip' in l.lower() for l in out.split('\n')):
    print('  NO IMS/VoLTE/VOIP settings in "secure"')

# Try setting it
print('\n  Trying: settings put secure ims_enabled 1')
out, err = adb('settings put secure ims_enabled 1')
print(f'  stdout: {out}')
print(f'  stderr: {err}')
out2, _ = adb('settings get secure ims_enabled')
print(f'  Verify get: {out2}')

print('\n  Trying: settings put secure volte_enabled 1')
out, err = adb('settings put secure volte_enabled 1')
print(f'  stdout: {out}')
print(f'  stderr: {err}')
out2, _ = adb('settings get secure volte_enabled')
print(f'  Verify get: {out2}')

# 2. Comprehensive getprop
print('\n[2] getprop - comprehensive IMS/VoLTE search')
out, _ = adb('getprop')
ims_props = []
for line in out.split('\n'):
    if any(k in line.lower() for k in ['ims', 'volte', 'voip', 'mmtel', 'ril.*voice', 'persist.*ims', 'persist.*ril']):
        ims_props.append(line.strip())
if ims_props:
    for p in ims_props:
        print(f'  {p}')
else:
    print('  NO matching properties found')

# Also check ril.ims specifically
print('\n  Specific: getprop | findstr "ril.ims"')
out, _ = adb('getprop | findstr /i "ril.ims"')
if out:
    for line in out.strip().split('\n'):
        print(f'  {line}')
else:
    print('  EMPTY')

print('\n  Specific: getprop | findstr "persist.sys.ims"')
out, _ = adb('getprop | findstr /i "persist.sys.ims"')
if out:
    for line in out.strip().split('\n'):
        print(f'  {line}')
else:
    print('  EMPTY')

print('\n  Specific: getprop | findstr "persist.vendor"')
out, _ = adb('getprop | findstr /i "persist.vendor"')
if out:
    for line in out.strip().split('\n'):
        print(f'  {line}')
else:
    print('  EMPTY')

# 3. dumpsys
print('\n[3] dumpsys - phone/subscription services')
out, _ = adb('dumpsys | findstr /i "phone\|subscription\|telephony\|ims\|radio"')
if out:
    for line in out.strip().split('\n'):
        print(f'  {line}')
else:
    print('  NO matching dumpsys services')

print('\n  dumpsys subscription:')
out, err = adb('dumpsys subscription')
print(f'  stdout lines: {len(out.split(chr(10)))}')
if 'not found' in out.lower() or 'error' in out.lower():
    print(f'  ERROR: {out[:500]}')
else:
    print(f'  First 300 chars: {out[:300]}')

print('\n  dumpsys iphonesubinfo:')
out, _ = adb('dumpsys iphonesubinfo')
print(f'  Output: {out[:500] if out else "EMPTY"}')

print('\n  dumpsys telephony.registry:')
out, _ = adb('dumpsys telephony.registry')
if out:
    # extract relevant lines
    for line in out.split('\n'):
        if any(k in line.lower() for k in ['ims', 'volte', 'simstate', 'phonestate', 'servicestate', 'data', 'voice', 'video']):
            print(f'  {line.strip()}')

# 4. cmd commands
print('\n[4] cmd commands')
print('  cmd phone:')
out, err = adb('cmd phone')
print(f'  {out[:500] if out else "EMPTY"}')

print('\n  cmd connectivity:')
out, err = adb('cmd connectivity')
if out:
    for line in out.split('\n'):
        if any(k in line.lower() for k in ['ims', 'volte', 'data', 'sim']):
            print(f'  {line.strip()}')
else:
    print('  EMPTY')

print('\n  cmd telephony:')
out, err = adb('cmd telephony')
print(f'  {out[:500] if out else "EMPTY"}')

# 5. content query - Samsung ContentProviders
print('\n[5] content query - Samsung ContentProviders')
providers = [
    'content://com.samsung.android.telephony/ims/',
    'content://com.samsung.android.samsungphone/ims/',
    'content://com.sec.android.app.samsungapps/ims/',
    'content://com.samsung.android.ril/ims/',
    'content://telephony/ims/',
    'content://telephony/sim/',
    'content://telephony/subscriptions/',
]
for uri in providers:
    out, err = adb(f'content query --uri "{uri}"')
    if 'error' in err.lower() or 'not found' in err.lower() or 'no permission' in err.lower():
        print(f'  {uri}: {err[:200]}')
    elif out:
        print(f'  {uri}: {out[:300]}')
    else:
        print(f'  {uri}: EMPTY')

# 6. Try am broadcast
print('\n[6] am broadcast - IMS intents')
broadcasts = [
    '-a com.samsung.android.ims.action.SET_IMS',
    '-a android.telephony.ims.action.SET_IMS',
    '-a android.telephony.action.CHANGE_SIM_PREFERRED',
]
for b in broadcasts:
    out, err = adb(f'am broadcast {b}')
    print(f'  {b}: err={err[:200] if err else "none"}')

# 7. settings global full list (for reference)
print('\n[7] settings global - full IMS-related keys')
out, _ = adb('settings list global')
ims_keys = []
for line in out.split('\n'):
    if any(k in line.lower() for k in ['ims', 'volte', 'voip', 'mmtel', 'preferred', 'sim', 'data_sim', 'voice_sim', 'sms_sim']):
        ims_keys.append(line.strip())
if ims_keys:
    for k in ims_keys:
        print(f'  {k}')
else:
    print('  NO IMS-related keys found')

print('\n' + '='*60)
print('INVESTIGATION COMPLETE')
print('='*60)
