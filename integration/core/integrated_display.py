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
    """
    Main display controller that handles image sequences, video playback,
    transitions, and depth-based interactions.
    """
    def __init__(self, config: IntegratedConfig, monitor_index: int = 1):
        """
        Initialize the display controller.
        
        Args:
            config: Application configuration instance
            monitor_index: Index of the monitor to use (default: 1)
        """
        self.logger = ConsoleLogger(name="Display")
        self.config = config
        self.terminal_context = None
       
        # Initialize core display components
        self.sdl_app = SDLApp(monitor_index, self.config)
        self.texture_manager = TextureManager(self.sdl_app.renderer)
        self.transition_manager = TransitionManager(self.sdl_app.renderer, self.config)
        self.stats = PlaybackStatistics()
        
        # Initialize sequence player with configuration
        self.sequence_player = ImageSequencePlayer(self.config, self.texture_manager)

        # Create shared adapter for depth processing
        self.depth_adapter = DepthMaskAdapter(logger=self.logger)
        
        # Initialize depth tracking system if enabled
        if self.config.enable_depth_tracking:
            self.depth_system = IntegratedDepth(self.config, self.depth_adapter)
        else:
            self.depth_system = None

        # Initialize SPADE system and sequence player if mask generation is enabled
        if self.config.enable_mask_generation:
            self.spade_system = IntegratedSpade(self.config)
            output_dir = str(self.config.spade_output_dir)
            self.logger.log(f"Setting output directory to: {output_dir}")
            self.sequence_player.set_directory(output_dir)
            self.sequence_player.start_loader_thread(1)
        else:
            self.spade_system = None
            
        # Timing and state tracking
        self.running = True
        self.last_update_time = 0
        self.last_source_frame_time = 0
        self.start_time = None
        self.frame_timer = 0.0
        self.current_frame = 0
        self.video_mode = False
        self.transition_active = False
        self.video_transition_triggered = False
        
        # Transition state
        self.fade_textures = []
        self.current_fade_index = 0
        
        # Frame interpolation state
        self.frame_in_sequence = 0
        self.interpolated_frames = []
        self.current_texture = None
        self.next_texture = None

        # Display resources
        self.overlay_texture = None
        self.depth_texture = None
        self.video_player = None

        # Timing configuration
        self.frame_timer = 0.0
        self.frame_duration = 1.0 / config.total_fps
        self.source_frame_duration = 1.0 / config.source_fps
        self.last_interpolation_time = 0.0
        self.interpolation_duration = self.source_frame_duration / (config.frames_to_interpolate + 1)
        
        self.frame_start_time = None
        self.frame_counter = 0
        self.next_frame_time = 0
        
        # Set up display geometry from config
        self.main_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )
        
        # Load initial overlay
        self._load_overlay()

    def _interpolate_textures(self, texture1, texture2, alpha):
        """
        Uproszczona interpolacja - tylko blend między teksturami
        """
        if not texture1 or not texture2:
            return None

        target = sdl2.SDL_CreateTexture(
            self.sdl_app.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, target)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)

        # Render first texture at full opacity
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture1, None, None)

        # Blend second texture
        sdl2.SDL_SetTextureBlendMode(texture2, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_SetTextureAlphaMod(texture2, int(alpha * 255))
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture2, None, None)

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, None)
        return target

    def _cleanup_interpolated_frames(self):
        """Clean up all interpolated frame textures."""
        for texture in self.interpolated_frames:
            sdl2.SDL_DestroyTexture(texture)
        self.interpolated_frames = []

    def _load_overlay(self):
        """Load overlay texture from current sequence configuration."""
        current_seq = self.config.get_current_sequence()
        if current_seq['overlay_path'] and os.path.exists(current_seq['overlay_path']):
            self.overlay_texture = self.texture_manager.load_image(
                current_seq['overlay_path'],
                self.config.final_resolution,
                keep_aspect=True
            )

    def initialize(self) -> bool:
        """
        Initialize display systems and resources.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self.config.enable_depth_tracking and not self.depth_system.start():
            self.logger.log("Failed to initialize depth tracking")
            return False

        # Initialize depth visualization texture
        self.depth_texture = sdl2.SDL_CreateTexture(
            self.sdl_app.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_STREAMING,
            self.main_rect.w,
            self.main_rect.h
        )
        
        return True
        """
        Główna pętla z precyzyjnym timerem
        """
        self.logger.log("Starting display.run()")
        with TerminalContext() as context:
            self.terminal_context = context
            if not self.initialize():
                return

            try:
                frame_time = 1.0 / self.config.total_fps
                self.logger.log(f"Frame time: {frame_time*1000:.1f}ms")
                
                while self.running and self.config.is_running:
                    current_time = time.time()
                    
                    self._handle_events()
                    if self._update(current_time):
                        self._render()
                        
                    # Process SPADE w osobnym wątku
                    if self.config.enable_mask_generation and self.spade_system:
                        self.spade_system.watch_and_process()
                    
                    # Oblicz dokładny czas snu
                    next_time = self.next_frame_time
                    sleep_time = next_time - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
            finally:
                self._cleanup()

    def _handle_events(self):
        """Process SDL events."""
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl2.SDL_QUIT:
                self.running = False
            elif event.type == sdl2.SDL_KEYDOWN:
                self._handle_keydown(event.key.keysym.sym)

    def _handle_keydown(self, key):
        """
        Handle keyboard input.
        
        Args:
            key: SDL keycode
        """
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
        """
        Check if video transition should be triggered.
        
        Returns:
            bool: True if video should start, False otherwise
        """
        if self.video_transition_triggered:
            return False
        
        current_time = time.time() - self.start_time
        should_trigger = current_time >= self.config.video_trigger_time

        if should_trigger:
            self.logger.log(f"Video trigger: time={current_time:.1f}s/{self.config.video_trigger_time}s")
            self.video_transition_triggered = True

        return should_trigger

    def _prepare_video_transition(self):
        """Prepare transition from image sequence to video playback."""
        if self.transition_active:
            return

        # Get last frame from sequence
        if not self.sequence_player.frame_buffer.empty():
            _, last_texture = self.sequence_player.frame_buffer.get()
            self.fade_textures = self.transition_manager.create_fade_to_white(
                last_texture,
                self.overlay_texture
            )
            self.logger.log(f"Created {len(self.fade_textures)} fade textures")
            sdl2.SDL_DestroyTexture(last_texture)
            self.current_fade_index = 0
            
            # Initialize video player
            current_seq = self.config.get_current_sequence()
            self.video_player = VideoPlayer(
                current_seq['video_path'],
                self.sdl_app.renderer,
                self.texture_manager
            )

    def _load_next_source_frame(self, current_time):
        """
        Load next source frame from sequence player.
        
        Args:
            current_time: Current system time
        """
        if not self.sequence_player.frame_buffer.empty():
            _, texture = self.sequence_player.frame_buffer.get()
            
            if self.current_texture is None:
                # First frame initialization
                self.current_texture = texture
                self.stats.update_source_frame()
                self.stats.update_display_frame()
                self.current_frame += 1
                self.last_source_frame_time = current_time
                
                if self.start_time is None:
                    self.start_time = current_time
                    self.last_update_time = self.start_time
                    self.stats.start_playback(self.start_time)
            else:
                # Store next frame and generate interpolations
                self.next_texture = texture
                self.stats.update_source_frame()
                self._generate_interpolation_frames()
                self.frame_in_sequence = 1

    def _move_to_next_source_frame(self, current_time):
        """Handle transition to next source frame with proper timing."""
        if not self.next_texture:
            return
            
        # Keep current frame timing until next source frame is ready
        if current_time - self.last_source_frame_time < self.source_frame_duration:
            return

        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
        self.current_texture = self.next_texture
        self.next_texture = None
        self.frame_in_sequence = 0
        self.last_source_frame_time = current_time
        self.last_interpolation_time = current_time

    def _generate_interpolation_frames(self):
        """
        Generuj wszystkie klatki interpolowane od razu
        """
        self._cleanup_interpolated_frames()
        
        if not self.current_texture or not self.next_texture:
            return
            
        for i in range(self.config.frames_to_interpolate):
            alpha = (i + 1) / (self.config.frames_to_interpolate + 1)
            texture = self._interpolate_textures(
                self.current_texture,
                self.next_texture,
                alpha
            )
            if texture:
                self.interpolated_frames.append(texture)
        """
        Uproszczona logika aktualizacji z dokładnym kontrolowaniem FPS
        """
        if self.frame_start_time is None:
            self.frame_start_time = current_time
            self.next_frame_time = current_time
            return False

        # Sprawdź czy czas na nową klatkę
        if current_time < self.next_frame_time:
            return False
            
        frame_interval = 1.0 / self.config.total_fps
        self.next_frame_time = self.frame_start_time + (self.frame_counter + 1) * frame_interval
        self.frame_counter += 1

        # Oblicz który frame w sekwencji powinien być teraz
        total_frames = self.config.frames_to_interpolate + 1
        sequence_time = (current_time - self.last_source_frame_time)
        sequence_position = sequence_time / (1.0 / self.config.source_fps)
        
        if sequence_position >= 1.0:
            # Czas na nową klatkę źródłową
            self._load_next_source_frame(current_time)
            return True
            
        # Oblicz który frame interpolowany
        interp_index = int(sequence_position * self.config.frames_to_interpolate)
        if interp_index < len(self.interpolated_frames):
            self._apply_interpolated_frame(interp_index)
        
        return True

    def _apply_interpolated_frame(self, index):
        """
        Apply an interpolated frame at the given index with proper timing.
        
        Args:
            index: Index of interpolated frame to apply
        """
        if index < len(self.interpolated_frames):
            new_texture = self.interpolated_frames[index]
            if new_texture:
                if self.current_texture:
                    sdl2.SDL_DestroyTexture(self.current_texture)
                self.current_texture = new_texture
                self.stats.update_display_frame()
                self.frame_in_sequence += 1
                self.last_interpolation_time = time.time()
                self.logger.log(f"Applied interpolated frame {index + 1}/{len(self.interpolated_frames)}")

    def _update_depth_texture(self, heatmap):
        """
        Update depth visualization texture with new heatmap data.
        
        Args:
            heatmap: numpy array containing depth visualization data
        """
        if not self.depth_texture or not heatmap.size:
            return
            
        pixels = heatmap.tobytes()
        pitch = self.main_rect.w * 4
        sdl2.SDL_UpdateTexture(self.depth_texture, None, pixels, pitch)

    def _update(self, current_time):
        """
        Uproszczona logika aktualizacji z dokładnym kontrolowaniem FPS
        """
        # Pierwsza inicjalizacja timera
        if self.frame_start_time is None:
            self.frame_start_time = current_time
            self.next_frame_time = current_time
            return False

        # Sprawdź czy czas na nową klatkę
        if current_time < self.next_frame_time:
            return False
                
        # Aktualizacja czasu następnej klatki
        frame_interval = 1.0 / self.config.total_fps
        self.next_frame_time = self.frame_start_time + (self.frame_counter + 1) * frame_interval
        self.frame_counter += 1

        # Jeśli nie mamy tekstury, załaduj pierwszą klatkę
        if self.current_texture is None:
            self._load_next_source_frame(current_time)
            return True

        # Sprawdź czy czas na nową klatkę źródłową
        source_elapsed = current_time - self.last_source_frame_time
        if source_elapsed >= self.source_frame_duration:
            if not self.sequence_player.frame_buffer.empty():
                _, texture = self.sequence_player.frame_buffer.get()
                
                # Usuń starą teksturę
                if self.current_texture:
                    sdl2.SDL_DestroyTexture(self.current_texture)
                    
                # Ustaw nową teksturę
                self.current_texture = texture
                self.last_source_frame_time = current_time
                self.stats.update_source_frame()
                self.stats.update_display_frame()
                self.current_frame += 1
                
                return True

        return True

    def run(self):
        """Główna pętla wyświetlania"""
        self.logger.log("Starting display.run()")
        with TerminalContext() as context:
            self.terminal_context = context
            if not self.initialize():
                return

            try:
                frame_time = 1.0 / self.config.total_fps
                self.logger.log(f"Frame time: {frame_time*1000:.1f}ms")
                
                while self.running and self.config.is_running:
                    current_time = time.time()
                    
                    self._handle_events()
                    
                    # Update i render
                    if self._update(current_time):
                        self._render()
                    
                    # SPADE w osobnym wątku
                    if self.config.enable_mask_generation and self.spade_system:
                        self.spade_system.watch_and_process()

                    # Oblicz czas snu
                    next_time = self.next_frame_time
                    sleep_time = next_time - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
            finally:
                self._cleanup()

    def _render(self):
        """Render current frame with all active components."""
        # Clear the renderer
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
        
        # Handle fade transition rendering
        if self.transition_active and self.fade_textures:
            self.logger.log(f"Rendering fade: index={self.current_fade_index}/{len(self.fade_textures)}")
            
            if self.current_fade_index < len(self.fade_textures):
                # Render current fade frame
                sdl2.SDL_RenderCopy(
                    self.sdl_app.renderer,
                    self.fade_textures[self.current_fade_index],
                    None,
                    None
                )
                self.current_fade_index += 1
            else:
                # Clean up fade textures when transition is complete
                self.logger.log("Cleaning up fade textures")
                for texture in self.fade_textures:
                    sdl2.SDL_DestroyTexture(texture)
                self.fade_textures = []
                self.current_fade_index = 0
                self.transition_active = False
        
        # Render current content texture
        if self.current_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.current_texture,
                None,
                self.main_rect
            )
            
        # Always render overlay on top
        if self.overlay_texture:
            sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.overlay_texture,
                None,
                None
            )

        # Render statistics if enabled
        if self.config.show_stats:
            stats_text = self.stats.format_stats()
            self.sdl_app.render_text(stats_text, 10, 10)
            
        # Present the rendered frame
        sdl2.SDL_RenderPresent(self.sdl_app.renderer)

    def _cleanup(self):
        """Clean up all resources before shutting down."""
        # Stop systems
        if self.config.enable_depth_tracking:
            self.depth_system.stop()

        if self.spade_system:
            self.spade_system.adapter.model = None
            
        if self.sequence_player:
            self.sequence_player.set_directory(None)  # Stop loader thread
        
        # Clean up textures
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