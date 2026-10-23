import sys
import asyncio
from PyQt6.QtWidgets import QApplication
import qasync

from ui.window import DynamicIsland
from system_media.media_manager import MediaManager

async def run_app():
    island = DynamicIsland()
    media_mgr = MediaManager()
    
    def on_space_pressed(): 
        asyncio.create_task(media_mgr.toggle_play_pause())
    
    island.space_pressed.connect(on_space_pressed)
    media_mgr.media_updated.connect(island.update_media)
    media_mgr.position_updated.connect(island.update_position)
    media_mgr.lyrics_updated.connect(island.update_lyrics)
    
    await media_mgr.init_manager()
    
    # If media is already active, update_media will have called island.show()
    # Otherwise island stays hidden until Spotify starts playing.
    
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass

def main():
    app = QApplication(sys.argv)
    # Prevent application from closing when island is hidden
    app.setQuitOnLastWindowClosed(False)
    
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    with loop:
        loop.run_until_complete(run_app())

if __name__ == "__main__":
    main()
