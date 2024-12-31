import sdl2
from ..config import AppConfig

class TransitionManager:
    """Handles transitions between different playback states"""
    def __init__(self, renderer, config):
        self.renderer = renderer
        self.config = config

    def ease_exponential_in(self, t):
        return 0 if t == 0 else pow(2, 10 * t - 10)
    
    def ease_exponential_out(self, t):
            return 1 if t == 1 else 1 - pow(2, -10 * t)

    def create_fade_from_white(self, image_texture, overlay_texture):
        """Creates a fade from white effect using exponential out easing"""
        num_steps = int(self.config.fade_duration * 60)
        fade_textures = []

        target = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution[0],
            self.config.final_resolution[1]
        )

        combined = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution[0],
            self.config.final_resolution[1]
        )

        white = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            1280
        )

        # Prepare white texture with black bars
        sdl2.SDL_SetRenderTarget(self.renderer, white)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        sdl2.SDL_SetRenderDrawColor(self.renderer, 255, 255, 255, 255)
        white_rect = sdl2.SDL_Rect(0, 40, self.config.final_resolution_model[0], 1200)
        sdl2.SDL_RenderFillRect(self.renderer, white_rect)
        sdl2.SDL_SetRenderTarget(self.renderer, None)

        # Prepare combined texture
        sdl2.SDL_SetRenderTarget(self.renderer, combined)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        dest_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            1280
        )

        sdl2.SDL_RenderCopy(self.renderer, image_texture, None, dest_rect)
        sdl2.SDL_SetTextureBlendMode(overlay_texture, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_RenderCopy(self.renderer, overlay_texture, None, None)
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_SetTextureBlendMode(combined, sdl2.SDL_BLENDMODE_BLEND)

        # Generate fade frames with exponential out easing
        for i in range(num_steps):
            progress = i / (num_steps - 1)
            eased_progress = self.ease_exponential_out(progress)

            sdl2.SDL_SetRenderTarget(self.renderer, target)
            sdl2.SDL_RenderClear(self.renderer)

            # Render combined image
            sdl2.SDL_RenderCopy(self.renderer, combined, None, None)

            # Apply white transition with inverse alpha
            sdl2.SDL_SetTextureBlendMode(white, sdl2.SDL_BLENDMODE_BLEND)
            sdl2.SDL_SetTextureAlphaMod(white, int((1 - eased_progress) * 255))
            sdl2.SDL_RenderCopy(self.renderer, white, None, dest_rect)

            frame = sdl2.SDL_CreateTexture(
                self.renderer,
                sdl2.SDL_PIXELFORMAT_RGBA8888,
                sdl2.SDL_TEXTUREACCESS_TARGET,
                self.config.final_resolution[0],
                self.config.final_resolution[1]
            )

            sdl2.SDL_SetTextureBlendMode(frame, sdl2.SDL_BLENDMODE_BLEND)
            sdl2.SDL_SetRenderTarget(self.renderer, frame)
            sdl2.SDL_RenderCopy(self.renderer, target, None, None)
            fade_textures.append(frame)

        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_DestroyTexture(target)
        sdl2.SDL_DestroyTexture(combined)
        sdl2.SDL_DestroyTexture(white)

        return fade_textures

    def create_fade_to_white(self, image_texture, overlay_texture):
        """Creates a fade to white effect over the specified duration"""
        num_steps = int(self.config.fade_duration * 60)
        fade_textures = []

        # Create target texture for full screen
        target = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution[0],
            self.config.final_resolution[1]
        )

        # Create texture for combined image and overlay (full screen)
        combined = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution[0],
            self.config.final_resolution[1]
        )

        # Create white texture for image area (3840x1280)
        white = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            1280
        )

        # Prepare white texture with black bars
        sdl2.SDL_SetRenderTarget(self.renderer, white)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        # White rectangle in the center (1200px)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 255, 255, 255, 255)
        white_rect = sdl2.SDL_Rect(0, 40, self.config.final_resolution_model[0], 1200)
        sdl2.SDL_RenderFillRect(self.renderer, white_rect)
        sdl2.SDL_SetRenderTarget(self.renderer, None)

        # Prepare combined texture with image and overlay
        sdl2.SDL_SetRenderTarget(self.renderer, combined)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        dest_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            1280
        )

        # Render image with black bars
        sdl2.SDL_RenderCopy(self.renderer, image_texture, None, dest_rect)

        # Apply overlay with blending
        sdl2.SDL_SetTextureBlendMode(overlay_texture, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_RenderCopy(self.renderer, overlay_texture, None, None)
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_SetTextureBlendMode(combined, sdl2.SDL_BLENDMODE_BLEND)

        # Generate fade frames
        for i in range(num_steps):
            progress = i / (num_steps - 1)
            eased_progress = self.ease_exponential_in(progress)

            # Set target and clear
            sdl2.SDL_SetRenderTarget(self.renderer, target)
            sdl2.SDL_RenderClear(self.renderer)

            # Render combined image
            sdl2.SDL_RenderCopy(self.renderer, combined, None, None)

            # Apply white transition only to image area
            sdl2.SDL_SetTextureBlendMode(white, sdl2.SDL_BLENDMODE_BLEND)
            sdl2.SDL_SetTextureAlphaMod(white, int(eased_progress * 255))
            sdl2.SDL_RenderCopy(self.renderer, white, None, dest_rect)

            # Create texture for this frame
            frame = sdl2.SDL_CreateTexture(
                self.renderer,
                sdl2.SDL_PIXELFORMAT_RGBA8888,
                sdl2.SDL_TEXTUREACCESS_TARGET,
                self.config.final_resolution[0],
                self.config.final_resolution[1]
            )

            sdl2.SDL_SetTextureBlendMode(frame, sdl2.SDL_BLENDMODE_BLEND)

            # Copy frame
            sdl2.SDL_SetRenderTarget(self.renderer, frame)
            sdl2.SDL_RenderCopy(self.renderer, target, None, None)

            fade_textures.append(frame)

        # Cleanup
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_DestroyTexture(target)
        sdl2.SDL_DestroyTexture(combined)
        sdl2.SDL_DestroyTexture(white)

        return fade_textures

    def create_white_transition_texture(self):
        """Creates a white texture with black bars for transition"""
        white_transition = sdl2.SDL_CreateTexture(
            self.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            1280
        )

        sdl2.SDL_SetRenderTarget(self.renderer, white_transition)

        # First all black
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        # Then white center
        sdl2.SDL_SetRenderDrawColor(self.renderer, 255, 255, 255, 255)
        white_rect = sdl2.SDL_Rect(0, 40, self.config.final_resolution_model[0], 1200)
        sdl2.SDL_RenderFillRect(self.renderer, white_rect)

        sdl2.SDL_SetRenderTarget(self.renderer, None)

        return white_transition
