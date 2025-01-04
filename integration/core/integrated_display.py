import time
import sdl2
import cv2
import os
import ctypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from .integrated_depth import IntegratedDepth
from .integrated_spade import IntegratedSpade
from apps.display.core import SDLApp, TextureManager, TransitionManager
from apps.display.players import VideoPlayer, ImageSequencePlayer
from apps.display.utils import PlaybackStatistics
from apps.depth_tracking.terminal_utils import TerminalContext
from integration.adapters.depth_mask_adapter import DepthMaskAdapter
from ..config import IntegratedConfig
from ..utils.console_logger import ConsoleLogger

class IntegratedDisplay:
    def __init__(self, config: IntegratedConfig, monitor_index: int = 1):
        self.logger = ConsoleLogger(name="Display")
        self.config = config
        self.terminal_context = None
        
        # Core display components
        self.sdl_app = SDLApp(monitor_index, self.config)
        self.texture_manager = TextureManager(self.sdl_app.renderer)
        self.sequence_player = ImageSequencePlayer(self.config, self.texture_manager)
        
        # Initialize subsystems
        self._init_subsystems()
        
        # Display state
        self._init_display_state()
        
        # Display geometry
        self.main_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )
        
        for file in self.config.spade_output_dir.glob('*.jpg'):
            try:
                file.unlink()
            except:
                pass
        
        self.stats = PlaybackStatistics()
        
    def _init_subsystems(self):
        # Initialize depth adapter
        self.depth_adapter = DepthMaskAdapter(logger=self.logger)
        
        # Initialize depth tracking if enabled
        self.depth_system = (
            IntegratedDepth(self.config, self.depth_adapter) 
            if self.config.enable_depth_tracking else None
        )
        
        # Initialize SPADE system if enabled
        self.spade_system = None
        if self.config.enable_mask_generation:
            self.spade_system = IntegratedSpade(self.config)
            self.sequence_player.set_directory(str(self.config.spade_output_dir))
            self.sequence_player.start_loader_thread(1)
            
    def _init_display_state(self):
        self.running = True
        self.sequence_start_time = None  # Timer dla aktualnej sekwencji
        self.current_texture = None
        self.depth_texture = None
        self.overlay_texture = None
        self._load_overlay()
        
    def initialize(self) -> bool:
        if self.config.enable_depth_tracking and not self.depth_system.start():
            self.logger.log("Failed to initialize depth tracking")
            return False
            
        if self.config.enable_depth_tracking:
            self.depth_texture = sdl2.SDL_CreateTexture(
                self.sdl_app.renderer,
                sdl2.SDL_PIXELFORMAT_RGBA8888,
                sdl2.SDL_TEXTUREACCESS_STREAMING,
                self.main_rect.w,
                self.main_rect.h
            )
            
        return True

    def run(self):
        self.logger.log("Starting display.run()")
        with TerminalContext() as context:
            self.terminal_context = context
            if not self.initialize():
                return

            try:
                self._run_display_loop()
            finally:
                self._cleanup()

    def _run_display_loop(self):
        while self.running and self.config.is_running:
            current_time = time.time()
            
            self._handle_events()
            if self._update(current_time):
                self._render()
                
            # Process SPADE if enabled
            if self.config.enable_mask_generation and self.spade_system:
                self.spade_system.watch_and_process()
            
            # Small sleep to prevent CPU overload
            time.sleep(0.01)

    def _handle_events(self):
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl2.SDL_QUIT:
                self.running = False
            elif event.type == sdl2.SDL_KEYDOWN:
                self._handle_keydown(event.key.keysym.sym)

    def _handle_keydown(self, key):
        if key in (sdl2.SDLK_ESCAPE, sdl2.SDLK_q):
            self.running = False
            self.config.is_running = False
        elif key == sdl2.SDLK_m:
            self.config.mirror_mode = not self.config.mirror_mode
            if self.depth_system:
                self.depth_system.update_config(self.config)
        elif key == sdl2.SDLK_d:
            self.config.show_visualization = not self.config.show_visualization
        elif key == sdl2.SDLK_w:
            self.config.display_window = not self.config.display_window
            if not self.config.display_window:
                cv2.destroyAllWindows()
        elif key == sdl2.SDLK_s:
            self.config.show_stats = not self.config.show_stats

    def _update(self, current_time: float) -> bool:
        # Inicjalizacja timera sekwencji
        if self.sequence_start_time is None:
            self.sequence_start_time = current_time

        # Sprawdź timeout sekwencji
        if current_time - self.sequence_start_time >= self.config.video_trigger_time:
            self._switch_sequence()
            return True

        # Sprawdź czy jest nowa klatka
        if not self.sequence_player.frame_buffer.empty():
            self._load_next_frame(current_time)
            return True

        return True

    def _load_next_frame(self, current_time: float):
        if self.sequence_player.frame_buffer.empty():
            return
            
        _, texture = self.sequence_player.frame_buffer.get()
        
        # Cleanup previous texture
        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
            
        self.current_texture = texture
        self.stats.update_source_frame()
        self.stats.update_display_frame()
        
        if not self.stats.start_time:
            self.stats.start_playback(current_time)


    def _render(self):
        # Clear renderer
        sdl2.SDL_SetRenderDrawColor(self.sdl_app.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)
        
        # Render depth visualization if enabled
        if self.config.show_visualization and self.depth_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.depth_texture,
                None,
                self.main_rect
            )
        
        # Render current content
        if self.current_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.current_texture,
                None,
                self.main_rect
            )
            
        # Render overlay
        if self.overlay_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.overlay_texture,
                None,
                None
            )
        
        if self.config.show_stats:
            stats_text = self.stats.format_stats()
            self.sdl_app.render_text(stats_text, 10, 10)
        
        # Present frame
        sdl2.SDL_RenderPresent(self.sdl_app.renderer)

    def _switch_sequence(self):
        """Switch to next sequence."""
        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
            self.current_texture = None
        
        next_seq = self.config.next_sequence()
        panorama_id = next_seq['image_directory'].split('/')[-2]
        
        # Reset
        self.depth_adapter.depth_tracker.position_counters = [0] * len(self.depth_adapter.depth_tracker.position_counters)
        self.sequence_player.start_loader_thread(1)
        
        for file in self.config.spade_output_dir.glob('*.jpg'):
            try:
                file.unlink()
            except:
                pass
        
        if self.spade_system:
            self.spade_system.file_counter = 1
        
        self.depth_adapter._initialize_mask_system(panorama_id=panorama_id)
        self.sequence_player.set_directory(str(self.config.spade_output_dir))
        
        self._load_overlay()
        self.sequence_start_time = time.time()
        self.logger.log(f"Switched to sequence: {panorama_id}")

    def _load_overlay(self):
        current_seq = self.config.get_current_sequence()
        if current_seq['overlay_path'] and os.path.exists(current_seq['overlay_path']):
            self.overlay_texture = self.texture_manager.load_image(
                current_seq['overlay_path'],
                self.config.final_resolution,
                keep_aspect=True
            )

    def _cleanup(self):
        if self.config.enable_depth_tracking:
            self.depth_system.stop()
            
        if self.spade_system:
            self.spade_system.adapter.model = None
            
        if self.sequence_player:
            self.sequence_player.set_directory(None)
        
        # Cleanup textures
        for texture in [self.depth_texture, self.current_texture, self.overlay_texture]:
            if texture:
                sdl2.SDL_DestroyTexture(texture)