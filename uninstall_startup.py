import os

def uninstall():
    startup_dir = os.path.join(os.environ['APPDATA'], r'Microsoft\Windows\Start Menu\Programs\Startup')
    shortcut_path = os.path.join(startup_dir, 'DynamicIsland.lnk')
    
    if os.path.exists(shortcut_path):
        try:
            os.remove(shortcut_path)
            print("[SUCCESS] Dynamic Island baslangictan kaldirildi.")
        except Exception as e:
            print(f"[ERROR] Dosya silinemedi: {e}")
    else:
        print("[INFO] Baslangicta kayitli Dynamic Island kisa yolu bulunamadi.")

if __name__ == '__main__':
    uninstall()
