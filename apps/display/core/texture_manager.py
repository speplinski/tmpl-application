import os
import sys
import ctypes
import sdl2
from PIL import Image

class TextureManager:
    def __init__(self, renderer):
        self.renderer = renderer

    def load_image(self, path, size, keep_aspect=True):
        if not os.path.exists(path):
            print(f"File not found: {path}")
            return None

        try:
            # Load and process image with PIL
            image = Image.open(path)
            image = image.convert('RGBA' if path.endswith('.png') else 'RGB')

            if keep_aspect:
                img_ratio = image.width / image.height
                target_ratio = size[0] / size[1]

                if img_ratio > target_ratio:
                    new_width = size[0]
                    new_height = int(size[0] / img_ratio)
                else:
                    new_height = size[1]
                    new_width = int(size[1] * img_ratio)

                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                new_img = Image.new(
                    'RGBA' if path.endswith('.png') else 'RGB', 
                    size, 
                    (0, 0, 0, 0 if path.endswith('.png') else 255)
                )
                paste_x = (size[0] - new_width) // 2
                paste_y = (size[1] - new_height) // 2
                new_img.paste(image, (paste_x, paste_y))
                image = new_img
            else:
                image = image.resize(size, Image.Resampling.LANCZOS)

            # Create SDL surface
            has_alpha = path.endswith('.png')
            depth = 32 if has_alpha else 24
            rmask = gmask = bmask = amask = 0

            if sys.byteorder == 'little':
                rmask, gmask, bmask, amask = 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000
            else:
                rmask, gmask, bmask, amask = 0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF

            surface = sdl2.SDL_CreateRGBSurface(
                0, image.width, image.height, depth,
                rmask, gmask, bmask, amask if has_alpha else 0
            )

            if not surface:
                print(f"Failed to create surface: {sdl2.SDL_GetError()}")
                return None

            # Copy pixel data
            pixels = image.tobytes()
            sdl2.SDL_LockSurface(surface)
            ctypes.memmove(surface.contents.pixels, pixels, len(pixels))
            sdl2.SDL_UnlockSurface(surface)

            # Create texture from surface
            texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)

            # Free surface
            sdl2.SDL_FreeSurface(surface)

            if not texture:
                print(f"Failed to create texture: {sdl2.SDL_GetError()}")
                return None

            return texture

        except Exception as e:
            print(f"Error loading image {path}: {e}")
            return None

    def create_texture_from_surface(self, surface, is_overlay=False):
        if not surface:
            return None

        texture = sdl2.SDL_CreateTextureFromSurface(self.renderer, surface)
        if not texture:
            print(f"Failed to create texture from surface: {sdl2.SDL_GetError()}")
            return None

        if texture and is_overlay:
            sdl2.SDL_SetTextureBlendMode(texture, sdl2.SDL_BLENDMODE_BLEND)
            sdl2.SDL_SetTextureAlphaMod(texture, 255)

        return texture
