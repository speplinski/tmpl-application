import time
import sdl2
import ctypes
from typing import Optional, Dict, Any
from pathlib import Path

from apps.display.core import SDLApp, TextureManager, TransitionManager
from apps.display.players import VideoPlayer, ImageSequencePlayer
from apps.display.utils import PlaybackStatistics
from ..config import IntegratedConfig 
from .integrated_depth import IntegratedDepth
from apps.depth_tracking.terminal_utils import TerminalContext

class IntegratedDisplay:
   def __init__(self, config: IntegratedConfig, monitor_index: int = 1):
       self.config = config
       self.terminal_context = None
       
       # Display initialization
       self.sdl_app = SDLApp(monitor_index)
       self.texture_manager = TextureManager(self.sdl_app.renderer)
       self.transition_manager = TransitionManager(self.sdl_app.renderer, self.config)
       self.stats = PlaybackStatistics()
       
       # Depth system
       self.depth_system = IntegratedDepth(config)
       
       # State tracking
       self.running = True
       self.video_mode = False
       self.transition_active = False
       self.last_update_time = time.time()
       
       # Display resources
       self.current_texture = None
       self.overlay_texture = None
       self.depth_texture = None
       
       # Display geometry 
       self.main_rect = sdl2.SDL_Rect(
           0, 
           0,
           self.config.grid_dimensions[0] * 80,  
           self.config.grid_dimensions[1] * 80
       )

   def initialize(self) -> bool:
       if not self.depth_system.start():
           print("Failed to initialize depth tracking")
           return False

       # Initialize SDL textures
       self._initialize_textures()
       return True

   def run(self):
       with TerminalContext() as context:
           self.terminal_context = context
           if not self.initialize():
               return

           try:
               while self.running:
                   current_time = time.time()
                   
                   if current_time - self.last_update_time < 1.0 / 60:
                       time.sleep(0.001)
                       continue
                       
                   self.last_update_time = current_time
                   self._handle_events()
                   self._update()
                   self._render()
                   
           finally:
               self._cleanup()

   def _initialize_textures(self):
       self.depth_texture = sdl2.SDL_CreateTexture(
           self.sdl_app.renderer,
           sdl2.SDL_PIXELFORMAT_RGBA8888,
           sdl2.SDL_TEXTUREACCESS_STREAMING,
           self.main_rect.w,
           self.main_rect.h
       )

       # Load overlay texture if configured
       overlay_path = Path(self.config.overlay_path) if hasattr(self.config, 'overlay_path') else None
       if overlay_path and overlay_path.exists():
           self.overlay_texture = self.texture_manager.load_image(
               str(overlay_path),
               self.config.final_resolution,
               keep_aspect=True
           )

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
       elif key == sdl2.SDLK_m:
           self.config.mirror_mode = not self.config.mirror_mode
           self.depth_system.update_config(self.config)
       elif key == sdl2.SDLK_d:
           self.config.show_visualization = not self.config.show_visualization
       elif key == sdl2.SDLK_w:
           self.config.display_window = not self.config.display_window
           if not self.config.display_window:
               cv2.destroyAllWindows()
       elif key == sdl2.SDLK_s:
           self.config.show_stats = not self.config.show_stats

   def _update(self):
       depth_data, heatmap = self.depth_system.get_latest_data()
       
       if depth_data:
           if self.config.show_visualization and heatmap is not None:
               self._update_depth_texture(heatmap)
               
           if not self.transition_active:
               active_positions = depth_data.get('active_positions', [])
               if self._check_transition_trigger(active_positions):
                   self._start_transition()

   def _update_depth_texture(self, heatmap):
       if not self.depth_texture or not heatmap.size:
           return
           
       pixels = heatmap.tobytes()
       pitch = self.main_rect.w * 4
       sdl2.SDL_UpdateTexture(self.depth_texture, None, pixels, pitch)

   def _check_transition_trigger(self, active_positions) -> bool:
       return len(active_positions) > 5

   def _start_transition(self):
       self.transition_active = True

   def _render(self):
       sdl2.SDL_SetRenderDrawColor(self.sdl_app.renderer, 0, 0, 0, 255)
       sdl2.SDL_RenderClear(self.sdl_app.renderer)
       
       if self.config.show_visualization and self.depth_texture:
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
               None
           )
           
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
       self.depth_system.stop()
       
       if self.depth_texture:
           sdl2.SDL_DestroyTexture(self.depth_texture)
       if self.current_texture:
           sdl2.SDL_DestroyTexture(self.current_texture)
       if self.overlay_texture:
           sdl2.SDL_DestroyTexture(self.overlay_texture)