import os
import sdl2
import sdl2.sdlttf
import ctypes
from ..config import AppConfig

class SDLApp:
    def __init__(self, monitor_index=1):
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

        config = AppConfig()
        sdl2.SDL_RenderSetLogicalSize(renderer, config.final_resolution[0], config.final_resolution[1])

        return window, renderer

    def _init_font(self):
        font_paths = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                font = sdl2.sdlttf.TTF_OpenFont(font_path.encode(), 24)
                if font:
                    return font
        return None

    def render_text(self, text, x, y, color=(255, 255, 255)):
        if not self.font:
            return None

        text_surface = sdl2.sdlttf.TTF_RenderText_Blended(
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

        w = ctypes.c_int()
        h = ctypes.c_int()
        sdl2.SDL_QueryTexture(text_texture, None, None, ctypes.byref(w), ctypes.byref(h))

        text_rect = sdl2.SDL_Rect(x, y, w.value, h.value)

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
