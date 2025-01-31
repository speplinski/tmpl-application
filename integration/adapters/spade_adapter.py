from typing import Optional, Union, List
import torch
import os
import sys
from pathlib import Path
import cv2
import numpy as np
import matplotlib.pyplot as plt
from apps.generator.utils.dynamic_config import get_project_root
from apps.spade.options.test_options import TestOptions
from apps.spade.models.pix2pix_model import Pix2PixModel

class SpadeAdapter:
    def __init__(self, device_type: str = 'auto', logger=None, bypass_spade: bool = False, colormap: str = 'viridis'):
        """
        Initialize SPADE adapter for processing masks.
        
        Args:
            device_type: Device to use ('cuda', 'mps', 'cpu' or 'auto')
            logger: Optional logger instance for logging
            bypass_spade: If True, bypass SPADE and directly colorize masks
            colormap: Colormap to use when bypassing SPADE
        """
        self.logger = logger
        self.device = self._setup_device(device_type)
        self.bypass_spade = bypass_spade
        self.colormap = colormap
        
        if self.logger:
            self.logger.log(f"Using device: {self.device}")
        
        if not self.bypass_spade:
            self.model = self._initialize_model()
        else:
            self.model = None
        
    def _setup_device(self, device_type: str) -> torch.device:
        """Setup computation device."""
        if device_type == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            elif torch.backends.mps.is_available():
                return torch.device('mps')
            else:
                return torch.device('cpu')
        return torch.device(device_type)

    def _initialize_model(self) -> Pix2PixModel:
        """Initialize SPADE model."""
        project_root = get_project_root()
        checkpoints_dir = project_root / 'checkpoints'
    
        original_argv = sys.argv
        sys.argv = [sys.argv[0]]  
    
        opt = TestOptions().parse()
        #opt.label_nc = 19
        #opt.ngf = 96
        #opt.batchSize = 1
        #opt.gpu_ids = -1
        opt.checkpoints_dir = str(checkpoints_dir)
        opt.name = 'tmpl'
        
        model = Pix2PixModel(opt)
        model.eval()
        model.to(self.device)
        
        sys.argv = original_argv
        
        if self.logger:
            self.logger.log("Model initialized successfully")
        return model
    
    def _colorize_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Colorize a grayscale mask using the specified colormap.
        
        Args:
            mask: Grayscale mask array
            
        Returns:
            Colorized mask as RGB image
        """
        # Normalize mask to 0-1 range
        min_val, max_val = np.min(mask), np.max(mask)
        
        if min_val == max_val:
            mask_norm = np.zeros_like(mask, dtype=float)
        else:
            mask_norm = (mask - min_val) / (max_val - min_val)

        # Apply colormap
        colormap = plt.get_cmap(self.colormap)
        colored = colormap(mask_norm)
        colored_rgb = (colored[:, :, :3] * 255).astype(np.uint8)
        
        return colored_rgb
        
    def process_mask(self, mask_path: Union[str, Path], output_path: Union[str, Path]) -> bool:
        """
        Process single segmentation mask through SPADE.
        
        Args:
            mask_path: Input mask path
            output_path: Output image path
            
        Returns:
            bool: True if successful
        """
        try:
            if self.logger:
                self.logger.log(f"Processing mask: {mask_path}")

            # Load mask
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                if self.logger:
                    self.logger.log(f"Failed to load mask: {mask_path}")
                return False

            if self.bypass_spade:
                # Direct colorization
                img = self._colorize_mask(mask)
            else:
                # Prepare data
                mask_tensor = torch.from_numpy(mask).unsqueeze(0).float().to(self.device)
                data = {
                    'label': mask_tensor.unsqueeze(0),
                    'instance': torch.zeros(1).to(self.device),
                    'image': torch.zeros(1, 3, mask.shape[0], mask.shape[1]).to(self.device)
                }

                # Generate
                with torch.no_grad():
                    if self.device.type == 'cuda':
                        with torch.cuda.amp.autocast():
                            generated = self.model(data, mode='inference')
                    else:
                        generated = self.model(data, mode='inference')

                # Process and save output
                img = ((generated[0].cpu().numpy() * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
                if img.shape[0] == 3:
                    img = img.transpose(1, 2, 0)
    
                # Cleanup
                del generated, data
                if self.device.type == 'cuda':
                    torch.cuda.empty_cache()
                elif self.device.type == 'mps':
                    torch.mps.empty_cache()
 
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save result
            cv2.imwrite(str(output_path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), 
                       [cv2.IMWRITE_JPEG_QUALITY, 95])

            if self.logger:
                self.logger.log(f"Saved result to: {output_path}")

            return True
            
        except Exception as e:
            error_msg = f"Error processing mask: {e}"
            if self.logger:
                self.logger.log(error_msg)
            else:
                print(error_msg)
            return False