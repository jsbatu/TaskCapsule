import os
import subprocess
import sys

def install():
    startup_dir = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')
    shortcut_path = os.path.join(startup_dir, 'DynamicIsland.lnk')
    
    pythonw_path = os.path.join(os.environ['LOCALAPPDATA'], r'Microsoft\WindowsApps\pythonw.exe')
    if not os.path.exists(pythonw_path):
        pythonw_path = 'pythonw.exe'

    target_dir = os.path.abspath(os.path.dirname(__file__))
    main_py = os.path.join(target_dir, 'main.py')

    ps_command = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{pythonw_path}'
$Shortcut.Arguments = '"{main_py}"'
$Shortcut.WorkingDirectory = '{target_dir}'
$Shortcut.Save()
"""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(shortcut_path):
        print("[SUCCESS] Dynamic Island baslangica eklendi!")
        print(f"Kisa yol: {shortcut_path}")
        print("Artik bilgisayar acildiginda arka planda otomatik calisacak ve Spotify acildiginda gorunecektir.")
    else:
        print("[ERROR] Kisa yol olusturulamadi:")
        print(result.stderr)

if __name__ == '__main__':
    install()
