import winreg
import os
import time
import glob

def parse_acf(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple ACF parser
    data = {}
    stack = [data]
    i = 0
    while i < len(content):
        if content[i].isspace():
            i += 1
            continue
        if content[i] == '"':
            i += 1
            key_start = i
            while content[i] != '"':
                i += 1
            key = content[key_start:i]
            i += 1  # skip "
            while content[i].isspace():
                i += 1
            if content[i] == '"':
                i += 1
                val_start = i
                while content[i] != '"':
                    i += 1
                val = content[val_start:i]
                i += 1  # skip "
                stack[-1][key] = val
            elif content[i] == '{':
                stack.append({})
                i += 1
            else:
                i += 1
        elif content[i] == '}':
            popped = stack.pop()
            if len(stack) > 0 and len(stack[-1]) > 0:
                last_key = list(stack[-1].keys())[-1]
                stack[-1][last_key] = popped
            i += 1
        else:
            i += 1
    return data

def get_dir_size(path):
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
    except Exception:
        pass
    return total

# Get Steam path from registry
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
except Exception:
    print("Could not find Steam installation.")
    exit(1)

# Get library folders
vdf_path = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
if not os.path.exists(vdf_path):
    print("Library folders file not found.")
    exit(1)

library_data = parse_acf(vdf_path)
libraries = [steam_path]
if 'libraryfolders' in library_data:
    for k in library_data['libraryfolders']:
        if k.isdigit() and 'path' in library_data['libraryfolders'][k]:
            libraries.append(library_data['libraryfolders'][k]['path'])

libraries = list(set(libraries))  # Unique paths

# Run for 5 minutes, output every minute
for minute in range(5):
    app_infos = []
    for lib in libraries:
        steamapps_dir = os.path.join(lib, 'steamapps')
        if not os.path.exists(steamapps_dir):
            continue
        for acf_file in glob.glob(os.path.join(steamapps_dir, 'appmanifest_*.acf')):
            try:
                data = parse_acf(acf_file)
                if 'AppState' in data:
                    app_state = data['AppState']
                    appid = app_state.get('appid', '')
                    name = app_state.get('name', 'Unknown')
                    state_flags = int(app_state.get('StateFlags', 0))
                    app_infos.append({
                        'appid': appid,
                        'name': name,
                        'state_flags': state_flags,
                        'lib': lib
                    })
            except Exception:
                pass

    # Find downloading apps
    downloading_apps = [app for app in app_infos if app['state_flags'] & 1048576 != 0]

    if not downloading_apps:
        print(f"Minute {minute+1}: No games are currently downloading.")
    else:
        # Get initial sizes
        start_sizes = {}
        for app in downloading_apps:
            download_dir = os.path.join(app['lib'], 'steamapps', 'downloading', app['appid'])
            if os.path.exists(download_dir):
                start_sizes[app['appid']] = get_dir_size(download_dir)

        # Wait 60 seconds
        time.sleep(60)

        # Get end sizes and calculate
        for app in downloading_apps:
            status = "Downloading"
            if app['state_flags'] & 512 != 0:
                status = "Paused"
            download_dir = os.path.join(app['lib'], 'steamapps', 'downloading', app['appid'])
            if os.path.exists(download_dir):
                end_size = get_dir_size(download_dir)
                delta_bytes = end_size - start_sizes.get(app['appid'], end_size)
                speed_mb_s = (delta_bytes / (1024 * 1024)) / 60 if delta_bytes > 0 else 0.0
                print(f"Minute {minute+1}: Game: {app['name']}, Status: {status}, Speed: {speed_mb_s:.2f} MB/s")
            else:
                print(f"Minute {minute+1}: Game: {app['name']}, Status: Not downloading")