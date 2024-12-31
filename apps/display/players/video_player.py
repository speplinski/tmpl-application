import av
import sdl2
from ..core.texture_manager import TextureManager

class VideoPlayer:
    """Handles video playback"""
    def __init__(self, video_path, renderer, texture_manager=None):
        self.video_path = video_path
        self.renderer = renderer
        self.texture_manager = texture_manager or TextureManager(renderer)
        self.texture = None
        self.video_finished = False
        self._init_video()

    def _init_video(self):
        try:
            self.container = av.open(self.video_path)
            self.stream = self.container.streams.video[0]
            self.stream.thread_type = 'AUTO'
            self.frame_iterator = self.container.decode(video=0)
        except Exception as e:
            print(f"Error initializing video player: {e}")
            raise

    def get_next_frame_texture(self):
        try:
            frame = next(self.frame_iterator)
            img = frame.to_ndarray(format='rgba')

            surface = sdl2.SDL_CreateRGBSurfaceFrom(
                img.ctypes.data, 
                frame.width, 
                frame.height, 
                32, 
                frame.width * 4,
                0x000000FF, 
                0x0000FF00, 
                0x00FF0000, 
                0xFF000000
            )

            if not surface:
                return None

            texture = self.texture_manager.create_texture_from_surface(surface)
            sdl2.SDL_FreeSurface(surface)
            return texture

        except StopIteration:
            self.video_finished = True
            return None
        except Exception as e:
            print(f"Error in get_next_frame_texture: {e}")
            return None