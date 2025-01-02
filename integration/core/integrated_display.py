import time
import sdl2
import os
import cv2
import ctypes
from typing import Optional, Dict, Any
from pathlib import Path

from apps.display.core import SDLApp, TextureManager, TransitionManager
from apps.display.players import VideoPlayer, ImageSequencePlayer
from apps.display.utils import PlaybackStatistics
from apps.depth_tracking.terminal_utils import TerminalContext
from ..config import IntegratedConfig 
from ..utils.console_logger import ConsoleLogger
from .integrated_depth import IntegratedDepth
from .integrated_spade import IntegratedSpade
from integration.adapters.depth_mask_adapter import DepthMaskAdapter

class IntegratedDisplay:
    def __init__(self, config: IntegratedConfig, monitor_index: int = 1):
        self.logger = ConsoleLogger(name="Display")
        self.config = config
        self.terminal_context = None
       
        # Display initialization
        self.sdl_app = SDLApp(monitor_index, self.config)
        self.texture_manager = TextureManager(self.sdl_app.renderer)
        self.transition_manager = TransitionManager(self.sdl_app.renderer, self.config)
        self.stats = PlaybackStatistics()
        
        # Initialize sequence player with app config
        self.sequence_player = ImageSequencePlayer(self.config, self.texture_manager)

        # Create shared adapter
        self.depth_adapter = DepthMaskAdapter(logger=self.logger)
        
        # Initialize depth system
        if self.config.enable_depth_tracking:
            self.depth_system = IntegratedDepth(self.config, self.depth_adapter)
        else:
            self.depth_system = None

        # Initialize SPADE and sequence player
        if self.config.enable_mask_generation:
            self.spade_system = IntegratedSpade(self.config)
            output_dir = str(self.config.spade_output_dir)
            self.logger.log(f"Setting output directory to: {output_dir}")
            self.sequence_player.set_directory(output_dir)
            self.sequence_player.start_loader_thread(1)
        else:
            self.spade_system = None
            
        # State tracking
        self.running = True
        self.last_update_time = time.time()
        self.start_time = time.time()
        self.current_frame = 0
        self.video_mode = False
        self.fade_textures = []
        self.current_fade_index = 0
        
        # Sequence interpolation state
        self.frame_in_sequence = 0
        self.interpolated_frames = []
        self.current_texture = None
        self.next_texture = None

        # Display resources
        self.overlay_texture = None
        self.depth_texture = None
        self.video_player = None

        # Display geometry from app config
        self.main_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )
        
        # Load initial overlay
        self._load_overlay()

    def _interpolate_textures(self, texture1, texture2, alpha):
        if not texture1 or not texture2:
            return None

        target = sdl2.SDL_CreateTexture(
            self.sdl_app.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )

        if not target:
            return None

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, target)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)

        # Render first texture
        sdl2.SDL_SetTextureAlphaMod(texture1, 255)
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture1, None, None)

        # Blend second texture with alpha
        sdl2.SDL_SetTextureBlendMode(texture2, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_SetTextureAlphaMod(texture2, int(alpha * 255))
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture2, None, None)

        # Reset blend modes
        sdl2.SDL_SetTextureAlphaMod(texture1, 255)
        sdl2.SDL_SetTextureAlphaMod(texture2, 255)

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, None)
        return target

    def _cleanup_interpolated_frames(self):
        for texture in self.interpolated_frames:
            sdl2.SDL_DestroyTexture(texture)
        self.interpolated_frames = []

    def _load_overlay(self):
        """Load overlay texture from current sequence."""
        current_seq = self.config.get_current_sequence()
        if current_seq['overlay_path'] and os.path.exists(current_seq['overlay_path']):
            self.overlay_texture = self.texture_manager.load_image(
                current_seq['overlay_path'],
                self.config.final_resolution,
                keep_aspect=True
            )

    def initialize(self) -> bool:
        if self.config.enable_depth_tracking and not self.depth_system.start():
            self.logger.log("Failed to initialize depth tracking")
            return False

        # Initialize depth texture
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
                target_frame_time = 1.0 / self.config.total_fps
                while self.running and self.config.is_running:
                    current_time = time.time()
                    frame_elapsed = current_time - self.last_update_time
                    
                    # Respect integrated refresh interval
                    if frame_elapsed < target_frame_time:
                        sleep_time = (target_frame_time - frame_elapsed) * 0.95
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                        continue
                        
                    self.last_update_time = current_time
                    self._handle_events()
                    self._update()
                    self._render()
                    
                    # Process SPADE if enabled and initialized
                    if self.config.enable_mask_generation and self.spade_system:
                        self.spade_system.watch_and_process()
                    
            finally:
                self._cleanup()

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

    def _check_video_trigger(self):
        """Check if video should start based on frame count or time."""
        current_time = time.time() - self.start_time
        return (self.current_frame >= self.config.video_trigger_frame or 
                current_time >= self.config.video_trigger_time)

    def _prepare_video_transition(self):
        """Prepare transition to video mode."""
        if not self.fade_textures:
            # Get last frame from sequence player
            if not self.sequence_player.frame_buffer.empty():
                _, last_texture = self.sequence_player.frame_buffer.get()
                self.fade_textures = self.transition_manager.create_fade_to_white(
                    last_texture,
                    self.overlay_texture
                )
                sdl2.SDL_DestroyTexture(last_texture)
                self.current_fade_index = 0
                
                # Initialize video player
                current_seq = self.config.get_current_sequence()
                self.video_player = VideoPlayer(
                    current_seq['video_path'],
                    self.sdl_app.renderer,
                    self.texture_manager
                )

    def _update(self):
        if self.config.enable_depth_tracking:
            depth_data, heatmap = self.depth_system.get_latest_data()
            
            if depth_data:
                if self.config.show_visualization and heatmap is not None:
                    self._update_depth_texture(heatmap)
                    
                # Check for activity-based video transition
                active_positions = depth_data.get('active_positions', [])
                if not self.video_mode and self._check_video_trigger():
                    self._prepare_video_transition()
                    self.video_mode = True

        # Check for time/frame based video transition
        if not self.video_mode and self._check_video_trigger():
            self._prepare_video_transition()
            self.video_mode = True

        # Update current texture based on mode
        if self.video_mode and self.video_player:
            if self.current_texture:
                sdl2.SDL_DestroyTexture(self.current_texture)
            new_texture = self.video_player.get_next_frame_texture()
            if new_texture:
                self.current_texture = new_texture
        else:
            # Try to get first frame if we don't have any texture yet
            if self.current_texture is None:
                if not self.sequence_player.frame_buffer.empty():
                    _, self.current_texture = self.sequence_player.frame_buffer.get()
                return

            # Sequence interpolation logic only when we have current texture
            if self.frame_in_sequence == 0:
                if not self.sequence_player.frame_buffer.empty():
                    if not self.stats.playing:
                        self.stats.start_playback()

                    # Get next frame
                    _, self.next_texture = self.sequence_player.frame_buffer.get()

                    # Generate interpolated frames
                    self._cleanup_interpolated_frames()
                    if self.current_texture and self.next_texture:
                        for i in range(self.config.frames_to_interpolate):
                            alpha = (i + 1) / (self.config.frames_to_interpolate + 1)
                            interpolated = self._interpolate_textures(
                                self.current_texture, 
                                self.next_texture, 
                                alpha
                            )
                            if interpolated:
                                self.interpolated_frames.append(interpolated)

                    if self.current_texture:
                        self.stats.total_source_frames += 1
                    self.frame_in_sequence = 1
                else:
                    if self.stats.playing:
                        self.stats.pause_playback()
            else:
                # Process interpolated frames
                if self.frame_in_sequence <= self.config.frames_to_interpolate:
                    interp_index = self.frame_in_sequence - 1
                    if interp_index < len(self.interpolated_frames):
                        if self.current_texture:
                            sdl2.SDL_DestroyTexture(self.current_texture)
                        self.current_texture = self.interpolated_frames[interp_index]
                    self.frame_in_sequence += 1
                else:
                    # Move to next frame
                    if self.current_texture:
                        sdl2.SDL_DestroyTexture(self.current_texture)
                    self.current_texture = self.next_texture
                    self.next_texture = None
                    self.frame_in_sequence = 0

        self.current_frame += 1

    def _update_depth_texture(self, heatmap):
        if not self.depth_texture or not heatmap.size:
            return
            
        pixels = heatmap.tobytes()
        pitch = self.main_rect.w * 4
        sdl2.SDL_UpdateTexture(self.depth_texture, None, pixels, pitch)

    def _render(self):
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
        
        if self.video_mode and self.fade_textures:
            # Render fade transition
            if self.current_fade_index < len(self.fade_textures):
                sdl2.SDL_RenderCopy(
                    self.sdl_app.renderer,
                    self.fade_textures[self.current_fade_index],
                    None,
                    None
                )
                self.current_fade_index += 1
        
        # Render current content if available
        if self.current_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.current_texture,
                None,
                self.main_rect
            )
            
        # Always render overlay
        if self.overlay_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.overlay_texture,
                None,
                None
            )

        # Render stats if enabled
        if self.config.show_stats:
            stats_text = self.stats.format_stats()
            self.sdl_app.render_text(stats_text, 10, 10)
            
        sdl2.SDL_RenderPresent(self.sdl_app.renderer)

    def _cleanup(self):
        if self.config.enable_depth_tracking:
            self.depth_system.stop()

        if self.spade_system:
            self.spade_system.adapter.model = None
            
        if self.sequence_player:
            self.sequence_player.set_directory(None)  # Stop loader thread
        
        # Clean up fade textures
        for texture in self.fade_textures:
            sdl2.SDL_DestroyTexture(texture)
        self.fade_textures.clear()
        
        if self.depth_texture:
            sdl2.SDL_DestroyTexture(self.depth_texture)
        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
        if self.overlay_texture:
            sdl2.SDL_DestroyTexture(self.overlay_texture)
        if self.video_player:
            del self.video_player