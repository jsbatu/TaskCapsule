import asyncio
import aiohttp
import re
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
from winrt.windows.storage.streams import Buffer
import time
import urllib.parse

class MediaManager(QObject):
    media_updated = pyqtSignal(dict)
    position_updated = pyqtSignal(float, float) # current, total
    lyrics_updated = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.manager = None
        self.current_session = None
        
        # Progress timer for smooth timeline scrubbing
        self.progress_timer = QTimer()
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._on_progress_timer)
        
        # Polling timer to catch Spotify opening/closing without delay
        self.session_poll_timer = QTimer()
        self.session_poll_timer.setInterval(1500)
        self.session_poll_timer.timeout.connect(self._on_poll_session)
        
        self.current_pos = 0
        self.total_pos = 0
        self.is_playing = False
        self.last_update_sys_time = 0
        self.last_track_id = ""

    async def init_manager(self):
        try:
            self.manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            if self.manager:
                self.manager.add_sessions_changed(self._on_sessions_changed)
                self._update_session()
                self.session_poll_timer.start()
        except Exception as e:
            print(f"[MediaManager] Init error: {e}")

    def _get_active_or_spotify_session(self):
        if not self.manager:
            return None
        try:
            # 1. Try Spotify specifically from all sessions
            sessions = self.manager.get_sessions()
            for s in sessions:
                try:
                    app_id = s.source_app_user_model_id.lower()
                    if "spotify" in app_id:
                        return s
                except Exception:
                    pass
            # 2. Fall back to the OS current session
            return self.manager.get_current_session()
        except Exception:
            return None

    def _update_session(self):
        new_session = self._get_active_or_spotify_session()
        if new_session:
            self.current_session = new_session
            self._bind_session(self.current_session)
            asyncio.create_task(self._update_media_info())
        else:
            self.current_session = None
            self.is_playing = False
            self.last_track_id = ""
            self.progress_timer.stop()
            self.media_updated.emit({"playing": False, "title": "", "artist": "", "thumbnail": b""})

    def _on_poll_session(self):
        active = self._get_active_or_spotify_session()
        # Check if session changed or became available/unavailable
        if active != self.current_session:
            self._update_session()
        elif active:
            # Periodically ensure media info is refreshed
            asyncio.create_task(self._update_media_info())

    def _on_sessions_changed(self, sender, args):
        self._update_session()

    def _bind_session(self, session):
        try:
            session.add_media_properties_changed(self._on_properties_changed)
            session.add_playback_info_changed(self._on_playback_changed)
            session.add_timeline_properties_changed(self._on_timeline_changed)
        except Exception:
            pass

    def _on_properties_changed(self, sender, args):
        asyncio.create_task(self._update_media_info())

    def _on_playback_changed(self, sender, args):
        asyncio.create_task(self._update_media_info())
        
    def _on_timeline_changed(self, sender, args):
        asyncio.create_task(self._update_timeline())

    async def _update_timeline(self):
        if not self.current_session: return
        try:
            timeline = self.current_session.get_timeline_properties()
            if timeline:
                self.current_pos = timeline.position.total_seconds()
                self.total_pos = timeline.end_time.total_seconds()
                self.last_update_sys_time = time.time()
                self.position_updated.emit(self.current_pos, self.total_pos)
        except Exception:
            pass

    def _on_progress_timer(self):
        if self.is_playing and self.total_pos > 0:
            elapsed_since_update = time.time() - self.last_update_sys_time
            pos = self.current_pos + elapsed_since_update
            if pos > self.total_pos:
                pos = self.total_pos
            self.position_updated.emit(pos, self.total_pos)

    async def _fetch_lyrics(self, title, artist):
        try:
            url = f"https://lrclib.net/api/get?track_name={urllib.parse.quote(title)}&artist_name={urllib.parse.quote(artist)}"
            headers = {'User-Agent': 'DynamicIsland/1.0'}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        synced = data.get("syncedLyrics", "")
                        if synced:
                            lines = []
                            for line in synced.split('\n'):
                                match = re.match(r'\[(\d+):(\d+\.\d+)\](.*)', line)
                                if match:
                                    m = int(match.group(1))
                                    s = float(match.group(2))
                                    raw_text = match.group(3).strip()
                                    clean_text = re.sub(r'[♪♫]', '', raw_text).strip()
                                    if clean_text:
                                        lines.append({'time': m*60 + s, 'text': clean_text})
                            self.lyrics_updated.emit(lines)
                            return
        except Exception as e:
            pass
        self.lyrics_updated.emit([])

    async def _update_media_info(self):
        if not self.current_session:
            return
        
        try:
            info = self.current_session.get_playback_info()
            props = await self.current_session.try_get_media_properties_async()
            
            self.is_playing = (info.playback_status == 4) if info else False
            
            await self._update_timeline()
            
            if self.is_playing:
                self.progress_timer.start()
            else:
                self.progress_timer.stop()
            
            title = props.title if props else ""
            artist = props.artist if props else ""
            
            track_id = f"{title}-{artist}"
            if track_id != self.last_track_id:
                self.last_track_id = track_id
                if title:
                    asyncio.create_task(self._fetch_lyrics(title, artist))
                else:
                    self.lyrics_updated.emit([])
            
            img_data = b""
            if props and props.thumbnail:
                try:
                    stream = await props.thumbnail.open_read_async()
                    buf = Buffer(stream.size)
                    await stream.read_async(buf, buf.capacity, 0)
                    img_data = bytes(memoryview(buf))
                except Exception:
                    pass
            
            self.media_updated.emit({
                "playing": self.is_playing,
                "title": title,
                "artist": artist,
                "thumbnail": img_data
            })
        except Exception as e:
            pass
        
    async def toggle_play_pause(self):
        if self.current_session:
            try:
                await self.current_session.try_toggle_play_pause_async()
            except Exception:
                pass
