import os
import time
import sdl2
import numpy as np
from threading import Thread, Lock
from queue import Queue
from PIL import Image
from integration.config import IntegratedConfig

class ImageSequencePlayer:
    def __init__(self, config: IntegratedConfig, texture_manager):
        self.config = config
        self.texture_manager = texture_manager
        self.frame_buffer = Queue(maxsize=config.depth.buffer_size)
        self.interpolation_buffer = Queue(maxsize=config.timing.frames_to_interpolate)
        self.buffer_lock = Lock()
        self.current_directory = None
        self._running = True
        self._loader_thread = None
        
        # Interpolation state
        self.current_frame_texture = None
        self.next_frame_texture = None
        self.current_frame_data = None
        self.next_frame_data = None
        self.interpolation_index = 0

    def _interpolate_frames(self, frame1_data, frame2_data, alpha):
        interpolated = frame1_data * (1 - alpha) + frame2_data * alpha
        interpolated = interpolated.astype(np.uint8)
        
        img = Image.fromarray(interpolated)
        
        surface = sdl2.SDL_CreateRGBSurfaceFrom(
            interpolated.ctypes.data,
            interpolated.shape[1],
            interpolated.shape[0],
            32,
            interpolated.shape[1] * 4,
            0xFF000000,
            0x00FF0000,
            0x0000FF00,
            0x000000FF
        )
        
        if not surface:
            return None
            
        texture = self.texture_manager.create_texture_from_surface(surface)
        sdl2.SDL_FreeSurface(surface)
        
        return texture

    def _generate_interpolation_frames(self):
        if not self.current_frame_data is None and not self.next_frame_data is None:
            while not self.interpolation_buffer.empty():
                old_texture = self.interpolation_buffer.get()
                sdl2.SDL_DestroyTexture(old_texture)
                
            for i in range(self.config.timing.frames_to_interpolate):
                alpha = (i + 1) / (self.config.timing.frames_to_interpolate + 1)
                texture = self._interpolate_frames(
                    self.current_frame_data,
                    self.next_frame_data,
                    alpha
                )
                if texture:
                    self.interpolation_buffer.put(texture)

    def get_next_display_frame(self):
        if not self.interpolation_buffer.empty():
            self.interpolation_index += 1
            return self.interpolation_buffer.get()
            
        if (self.current_frame_texture is None or 
            self.interpolation_index >= self.config.timing.frames_to_interpolate):
            
            if self.current_frame_texture:
                sdl2.SDL_DestroyTexture(self.current_frame_texture)
            
            self.current_frame_texture = self.next_frame_texture
            self.current_frame_data = self.next_frame_data
            
            if not self.frame_buffer.empty():
                _, self.next_frame_texture = self.frame_buffer.get()
                
                surface = sdl2.SDL_CreateRGBSurface(
                    0,
                    self.config.display.model_resolution[0],
                    self.config.display.model_resolution[1],
                    32,
                    0xFF000000,
                    0x00FF0000,
                    0x0000FF00,
                    0x000000FF
                )
                
                sdl2.SDL_RenderReadPixels(
                    self.texture_manager.renderer,
                    None,
                    sdl2.SDL_PIXELFORMAT_RGBA8888,
                    surface.contents.pixels,
                    surface.contents.pitch
                )
                
                self.next_frame_data = np.frombuffer(
                    surface.contents.pixels, 
                    dtype=np.uint8
                ).reshape(
                    self.config.display.model_resolution[1],
                    self.config.display.model_resolution[0],
                    4
                )
                
                sdl2.SDL_FreeSurface(surface)
                
                self._generate_interpolation_frames()
                self.interpolation_index = 0
            
        return self.current_frame_texture

    def start_loader_thread(self, start_index):
        self._running = True
        self._loader_thread = Thread(
            target=self._buffer_loader_thread,
            args=(start_index,),
            daemon=True
        )
        self._loader_thread.start()

    def _stop_loader_thread(self):
        """Safely stop the loader thread."""
        self._running = False
        if self._loader_thread:
            self._loader_thread.join()
            self._loader_thread = None

    def _buffer_loader_thread(self, start_index):
        current_index = start_index
        frame_interval = 1.0 / self.config.timing.source_fps
        last_frame_time = time.time()

        while self._running:
            current_time = time.time()
            if current_time - last_frame_time >= frame_interval:
                if self.frame_buffer.full():
                    time.sleep(frame_interval * 0.1)
                    continue

                if not self.current_directory:
                    time.sleep(0.1)
                    continue
                
                image_path = os.path.join(
                    str(self.current_directory),
                    f"{current_index:09d}.jpg"
                )

                if not os.path.exists(image_path):
                    time.sleep(0.1)
                    continue

                texture = self.texture_manager.load_image(
                    image_path, 
                    self.config.display.model_resolution, 
                    keep_aspect=True
                )

                if texture:
                    self.frame_buffer.put((current_index, texture))
                    current_index += self.config.timing.frame_step
                    last_frame_time = current_time
                else:
                    time.sleep(0.1)

                buffer_fill = self.frame_buffer.qsize() / self.config.depth.buffer_size
                sleep_time = frame_interval * (0.1 if buffer_fill > 0.8 else 0.5)
                time.sleep(sleep_time)

            time.sleep(0.001)

    def set_directory(self, new_directory):
        """Set new directory and properly clean up old state."""
        self._stop_loader_thread()
        
        with self.buffer_lock:
            # Clear frame buffer
            while not self.frame_buffer.empty():
                _, texture = self.frame_buffer.get()
                sdl2.SDL_DestroyTexture(texture)
                
            # Clear interpolation buffer
            while not self.interpolation_buffer.empty():
                texture = self.interpolation_buffer.get()
                sdl2.SDL_DestroyTexture(texture)
            
            # Clean up current/next frame state
            if self.current_frame_texture:
                sdl2.SDL_DestroyTexture(self.current_frame_texture)
            if self.next_frame_texture:
                sdl2.SDL_DestroyTexture(self.next_frame_texture)
                
            self.current_frame_texture = None
            self.next_frame_texture = None
            self.current_frame_data = None
            self.next_frame_data = None
            self.interpolation_index = 0

            # Set new directory last
            self.current_directory = new_directory