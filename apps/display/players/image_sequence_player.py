import os
import time
import sdl2
from threading import Thread, Lock
from queue import Queue
from ..config import AppConfig

class ImageSequencePlayer:
    """Handles image sequence playback with interpolation"""
    def __init__(self, config, texture_manager):
        self.config = config
        self.texture_manager = texture_manager
        self.frame_buffer = Queue(maxsize=config.buffer_size)
        self.buffer_lock = Lock()

    def start_loader_thread(self, start_index):
        loader_thread = Thread(
            target=self._buffer_loader_thread, 
            args=(start_index,), 
            daemon=True
        )
        loader_thread.start()

    def _buffer_loader_thread(self, start_index):
        current_index = start_index
        frame_interval = 1.0 / self.config.source_fps
        last_frame_time = time.time()

        while True:
            current_time = time.time()

            if current_time - last_frame_time >= frame_interval:
                if self.frame_buffer.full():
                    time.sleep(0.1)
                    continue

                image_path = os.path.join(
                    self.config.image_directory, 
                    f"{current_index:09d}.jpg"
                )

                if not os.path.exists(image_path):
                    time.sleep(0.5)
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
                    time.sleep(0.5)

            time.sleep(0.001)

    def set_directory(self, new_directory):
        with self.buffer_lock:
            # Clear existing buffer
            while not self.frame_buffer.empty():
                _, texture = self.frame_buffer.get()
                sdl2.SDL_DestroyTexture(texture)
        self.config.image_directory = new_directory