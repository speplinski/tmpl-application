import os
import sdl2
import sdl2.sdlttf
import ctypes
from integration.config import IntegratedConfig

class SDLApp:
    def __init__(self, monitor_index: int, config: IntegratedConfig):
        self.config = config
        self._init_sdl()
        self.window, self.renderer = self._create_window_and_renderer(monitor_index)
        self.font = self._init_font()

    def _init_sdl(self):
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise Exception(sdl2.SDL_GetError())
        if sdl2.sdlttf.TTF_Init() != 0:
            raise Exception(sdl2.sdlttf.TTF_GetError())

    def _create_window_and_renderer(self, monitor_index):
        num_displays = sdl2.SDL_GetNumVideoDisplays()
        if monitor_index >= num_displays:
            print(f"Warning: Monitor {monitor_index} not found. Using monitor 0.")
            monitor_index = 0

        display_bounds = sdl2.SDL_Rect()
        sdl2.SDL_GetDisplayBounds(monitor_index, ctypes.byref(display_bounds))

        window = sdl2.SDL_CreateWindow(
            b"The Most Polish Landscape",
            display_bounds.x,
            display_bounds.y,
            display_bounds.w,
            display_bounds.h,
            sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP
        )

        if not window:
            raise Exception(sdl2.SDL_GetError())

        renderer = sdl2.SDL_CreateRenderer(
            window, -1,
            sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
        )

        if not renderer:
            raise Exception(sdl2.SDL_GetError())

        renderer_info = sdl2.SDL_RendererInfo()
        sdl2.SDL_GetRendererInfo(renderer, renderer_info)
        if not (renderer_info.flags & sdl2.SDL_RENDERER_PRESENTVSYNC):
            print("Warning: VSYNC not available")

        sdl2.SDL_RenderSetLogicalSize(
            renderer, 
            self.config.display.resolution[0], 
            self.config.display.resolution[1]
        )

        return window, renderer

    def _init_font(self):
        font_paths = [
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/System/Library/Fonts/SFNSMono.ttf", 
            "/System/Library/Fonts/Monaco.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                font = sdl2.sdlttf.TTF_OpenFont(font_path.encode(), 36)
                if font:
                    print(f"Using font: {font_path}")
                    return font
        return None

    def render_text(self, text, x, y, color=(255, 255, 255)):
        if not self.font:
            return None

        text_surface = sdl2.sdlttf.TTF_RenderText_Solid(
            self.font,
            text.encode(),
            sdl2.SDL_Color(color[0], color[1], color[2], 255)
        )

        if not text_surface:
            return None

        text_texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, text_surface)

        if not text_texture:
            sdl2.SDL_FreeSurface(text_surface)
            return None

        sdl2.SDL_SetTextureBlendMode(text_texture, sdl2.SDL_BLENDMODE_NONE)
        
        w = text_surface.contents.w
        h = text_surface.contents.h
        text_rect = sdl2.SDL_Rect(x, y, w, h)
        
        sdl2.SDL_RenderCopy(self.renderer, text_texture, None, text_rect)

        sdl2.SDL_FreeSurface(text_surface)
        sdl2.SDL_DestroyTexture(text_texture)

    def __del__(self):
        if hasattr(self, 'font') and self.font:
            sdl2.sdlttf.TTF_CloseFont(self.font)
        if hasattr(self, 'renderer') and self.renderer:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if hasattr(self, 'window') and self.window:
            sdl2.SDL_DestroyWindow(self.window)
        sdl2.sdlttf.TTF_Quit()
        sdl2.SDL_Quit()