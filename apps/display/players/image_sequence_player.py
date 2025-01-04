import os
import time
import sdl2
import numpy as np
from threading import Thread, Lock
from queue import Queue
from PIL import Image
from integration.config import IntegratedConfig

class ImageSequencePlayer:
    """Handles image sequence playback with interpolation"""
    def __init__(self, config: IntegratedConfig, texture_manager):
        self.config = config
        self.texture_manager = texture_manager
        self.frame_buffer = Queue(maxsize=config.buffer_size)
        self.interpolation_buffer = Queue(maxsize=config.frames_to_interpolate)
        self.buffer_lock = Lock()
        self.current_directory = None
        
        # Interpolation state
        self.current_frame_texture = None
        self.next_frame_texture = None
        self.current_frame_data = None
        self.next_frame_data = None
        self.interpolation_index = 0

    def _interpolate_frames(self, frame1_data, frame2_data, alpha):
        """
        Interpolate between two frames using linear interpolation
        
        Args:
            frame1_data: NumPy array of first frame
            frame2_data: NumPy array of second frame
            alpha: Interpolation factor (0.0 - 1.0)
            
        Returns:
            Interpolated frame as SDL texture
        """
        # Linear interpolation between frames
        interpolated = frame1_data * (1 - alpha) + frame2_data * alpha
        interpolated = interpolated.astype(np.uint8)
        
        # Create PIL image from array
        img = Image.fromarray(interpolated)
        
        # Convert to SDL texture
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
        """Generate interpolation frames between current and next frame"""
        if not self.current_frame_data is None and not self.next_frame_data is None:
            # Clear existing interpolation buffer
            while not self.interpolation_buffer.empty():
                old_texture = self.interpolation_buffer.get()
                sdl2.SDL_DestroyTexture(old_texture)
                
            # Generate new interpolation frames
            for i in range(self.config.frames_to_interpolate):
                alpha = (i + 1) / (self.config.frames_to_interpolate + 1)
                texture = self._interpolate_frames(
                    self.current_frame_data,
                    self.next_frame_data,
                    alpha
                )
                if texture:
                    self.interpolation_buffer.put(texture)

    def get_next_display_frame(self):
        """
        Get next frame to display, either interpolated or source frame
        
        Returns:
            SDL texture of next frame to display
        """
        # If we have interpolated frames, return the next one
        if not self.interpolation_buffer.empty():
            self.interpolation_index += 1
            return self.interpolation_buffer.get()
            
        # If we need to load new source frames
        if self.current_frame_texture is None or self.interpolation_index >= self.config.frames_to_interpolate:
            # Move to next source frame pair
            if self.current_frame_texture:
                sdl2.SDL_DestroyTexture(self.current_frame_texture)
            
            self.current_frame_texture = self.next_frame_texture
            self.current_frame_data = self.next_frame_data
            
            # Get next frame from buffer
            if not self.frame_buffer.empty():
                _, self.next_frame_texture = self.frame_buffer.get()
                
                # Convert texture to array for interpolation
                surface = sdl2.SDL_CreateRGBSurface(
                    0,
                    self.config.final_resolution_model[0],
                    self.config.final_resolution_model[1],
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
                    self.config.final_resolution_model[1],
                    self.config.final_resolution_model[0],
                    4
                )
                
                sdl2.SDL_FreeSurface(surface)
                
                # Generate new interpolation frames
                self._generate_interpolation_frames()
                self.interpolation_index = 0
            
        return self.current_frame_texture

    def start_loader_thread(self, start_index):
        """Start background thread for loading source frames"""
        loader_thread = Thread(
            target=self._buffer_loader_thread,
            args=(start_index,),
            daemon=True
        )
        loader_thread.start()

    def _buffer_loader_thread(self, start_index):
        """Background thread for loading source frames"""
        current_index = start_index
        frame_interval = 1.0 / self.config.source_fps
        last_frame_time = time.time()

        while True:
            current_time = time.time()
            if current_time - last_frame_time >= frame_interval:
                if self.frame_buffer.full():
                    time.sleep(frame_interval * 0.1)
                    continue

                current_seq = self.config.get_current_sequence()
                if not current_seq or not self.current_directory:
                    time.sleep(0.1)
                    continue
                
                image_path = os.path.join(
                    str(self.current_directory),
                    f"{current_index:09d}.jpg"
                )

                #self.logger.log(f"--- Looking for file: {image_path}")
                if not os.path.exists(image_path):
                    time.sleep(0.1)
                    continue

                texture = self.texture_manager.load_image(
                    image_path, 
                    self.config.final_resolution_model, 
                    keep_aspect=True
                )

                if texture:
                    self.frame_buffer.put((current_index, texture))
                    current_index += self.config.frame_step
                    last_frame_time = current_time
                else:
                    time.sleep(0.1)

                # Adaptive sleep based on buffer fill level
                buffer_fill = self.frame_buffer.qsize() / self.config.buffer_size
                sleep_time = frame_interval * (0.1 if buffer_fill > 0.8 else 0.5)
                time.sleep(sleep_time)

            time.sleep(0.001)

    def set_directory(self, new_directory):
        """Change the source directory and clear buffers"""
        with self.buffer_lock:
            # Clear existing buffers
            while not self.frame_buffer.empty():
                _, texture = self.frame_buffer.get()
                sdl2.SDL_DestroyTexture(texture)
                
            while not self.interpolation_buffer.empty():
                texture = self.interpolation_buffer.get()
                sdl2.SDL_DestroyTexture(texture)
            
            # Reset interpolation state
            if self.current_frame_texture:
                sdl2.SDL_DestroyTexture(self.current_frame_texture)
            if self.next_frame_texture:
                sdl2.SDL_DestroyTexture(self.next_frame_texture)
                
            self.current_frame_texture = None
            self.next_frame_texture = None
            self.current_frame_data = None
            self.next_frame_data = None
            self.interpolation_index = 0

            # Update directory
            self.current_directory = new_directory