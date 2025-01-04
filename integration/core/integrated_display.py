import time
import sdl2
import cv2
import os
import json
import ctypes
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from .integrated_depth import IntegratedDepth
from .integrated_spade import IntegratedSpade
from apps.display.core import SDLApp, TextureManager
from apps.display.players import VideoPlayer, ImageSequencePlayer
from apps.display.utils import PlaybackStatistics
from apps.depth_tracking.terminal_utils import TerminalContext
from integration.adapters.depth_mask_adapter import DepthMaskAdapter
from apps.generator.utils.dynamic_config import get_project_root
from ..config import IntegratedConfig
from ..utils.console_logger import ConsoleLogger

class IntegratedDisplay:
    def __init__(self, config: IntegratedConfig, monitor_index: int = 1):
        self.logger = ConsoleLogger(name="Display")
        self.config = config
        self.terminal_context = None
        
        # Core display components
        self.sdl_app = SDLApp(monitor_index, config)
        self.texture_manager = TextureManager(self.sdl_app.renderer)
        self.sequence_player = ImageSequencePlayer(config, self.texture_manager)
        
        self._init_subsystems()
        self._init_display_state()
        
        # Display geometry
        self.main_rect = sdl2.SDL_Rect(
            0, 
            self.config.display.resolution_offset,
            self.config.display.model_resolution[0],
            self.config.display.model_resolution[1]
        )
        
        # Clean output directory
        for file in self.config.spade.output_dir.glob('*.jpg'):
            try:
                file.unlink()
            except:
                pass
        
        self.stats = PlaybackStatistics()
        
    def _init_subsystems(self):
        self.depth_adapter = DepthMaskAdapter(config=self.config, logger=self.logger)
        
        self.depth_system = (
            IntegratedDepth(self.config, self.depth_adapter) 
            if self.config.enable_depth_tracking else None
        )
        
        if self.config.enable_mask_generation:
            self.spade_system = IntegratedSpade(self.config)
            self.sequence_player.set_directory(str(self.config.spade.output_dir))
            self.sequence_player.start_loader_thread(1)
        else:
            self.spade_system = None

    def _init_display_state(self):
        self.running = True
        self.sequence_start_time = None
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
                
            if self.config.enable_mask_generation and self.spade_system:
                self.spade_system.watch_and_process()
            
            time.sleep(self.config.timing.refresh_interval)

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
            self.config.depth.mirror_mode = not self.config.depth.mirror_mode
            if self.depth_system:
                self.depth_system.update_config(self.config)
        elif key == sdl2.SDLK_d:
            self.config.display.show_visualization = not self.config.display.show_visualization
        elif key == sdl2.SDLK_w:
            self.config.depth.display_window = not self.config.depth.display_window
            if not self.config.depth.display_window:
                cv2.destroyAllWindows()
        elif key == sdl2.SDLK_s:
            self.config.display.show_stats = not self.config.display.show_stats

    def _update(self, current_time: float) -> bool:
        if self.sequence_start_time is None:
            self.sequence_start_time = current_time

        if current_time - self.sequence_start_time >= self.config.timing.video_trigger:
            self._switch_sequence()
            return True

        if not self.sequence_player.frame_buffer.empty():
            self._load_next_frame(current_time)
            return True

        return True

    def _load_next_frame(self, current_time: float):
        if self.sequence_player.frame_buffer.empty():
            return
            
        _, texture = self.sequence_player.frame_buffer.get()
        
        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
            
        self.current_texture = texture
        self.stats.update_source_frame()
        self.stats.update_display_frame()
        
        if not self.stats.start_time:
            self.stats.start_playback(current_time)

    def _render(self):
        sdl2.SDL_SetRenderDrawColor(self.sdl_app.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)
        
        if self.config.display.show_visualization and self.depth_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.depth_texture,
                None,
                self.main_rect
            )
        
        if self.current_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.current_texture,
                None,
                self.main_rect
            )
            
        if self.overlay_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.overlay_texture,
                None,
                None
            )
        
        if self.config.display.show_stats:
            stats_text = self.stats.format_stats()
            self.sdl_app.render_text(stats_text, 10, 10)
        
        sdl2.SDL_RenderPresent(self.sdl_app.renderer)

    def _reset_tracking_state(self):
        """Reset tracking state before switching sequence."""
        if self.depth_adapter:
            self.depth_adapter.depth_tracker.position_counters = [0] * len(
                self.depth_adapter.depth_tracker.position_counters
            )
            self.depth_adapter.depth_tracker.position_timers.clear()
            self.depth_adapter.depth_tracker._active_columns.clear()
            
    def _clean_output_directory(self):
        """Clean output directory before switching sequence."""
        for file in self.config.spade.output_dir.glob('*.jpg'):
            try:
                file.unlink()
            except Exception as e:
                self.logger.log(f"Error cleaning output file: {e}")

    def _switch_sequence(self):
        """Handle clean transition between sequences."""
        try:
            # Get next panorama_id
            project_root = get_project_root()
            mapping_path = project_root / 'data' / 'mask_mapping.json'
            
            with open(mapping_path) as f:
                mask_mappings = json.load(f)
                
            current_id = self.spade_system.current_panorama_id
            self.logger.log(f"Current ID: {current_id}")
            
            panorama_ids = list(mask_mappings.keys())
            self.logger.log(f"Available panoramas: {panorama_ids}") 
            
            current_idx = panorama_ids.index(current_id)
            self.logger.log(f"Current index: {current_idx}")
            
            next_idx = (current_idx + 1) % len(panorama_ids)
            next_panorama = panorama_ids[next_idx]
            self.spade_system.current_panorama_id = next_panorama
            self.logger.log(f"Next index: {next_idx}, Next panorama: {next_panorama}")
            
            # Update config with new sequence path
            self.config.sequence.image_directory = f"data/sequences/{next_panorama}/"
            self.config.sequence.overlay_path = f"data/overlays/{next_panorama}.png"
            
            # Cleanup current state
            if self.current_texture:
                sdl2.SDL_DestroyTexture(self.current_texture)
                self.current_texture = None
            
            # Initialize new sequence
            self.depth_adapter._initialize_mask_system(panorama_id=next_panorama)
            
            # Reset states
            self._reset_tracking_state()
            if self.spade_system:
                self.spade_system.reset_state()
            self._clean_output_directory()
            
            # Setup output directory and sequence player
            output_dir = str(self.config.spade.output_dir)
            os.makedirs(output_dir, exist_ok=True)
            
            self.sequence_player.set_directory(output_dir)
            self._load_overlay()
            
            # Restart loader thread
            self.sequence_player.start_loader_thread(1)
            
            self.sequence_start_time = time.time()
            self.logger.log(f"Switched to sequence: {next_panorama}")
            
        except Exception as e:
            self.logger.log(f"Error during sequence transition: {e}")

    def _load_overlay(self):
        if os.path.exists(self.config.sequence.overlay_path):
            self.overlay_texture = self.texture_manager.load_image(
                self.config.sequence.overlay_path,
                self.config.display.resolution,
                keep_aspect=True
            )

    def _cleanup(self):
        if self.config.enable_depth_tracking:
            self.depth_system.stop()
            
        if self.spade_system:
            self.spade_system.adapter.model = None
            
        if self.sequence_player:
            self.sequence_player.set_directory(None)
        
        for texture in [self.depth_texture, self.current_texture, self.overlay_texture]:
            if texture:
                sdl2.SDL_DestroyTexture(texture)