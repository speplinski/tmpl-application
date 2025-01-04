from typing import Optional, Union
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
    def __init__(self, config, logger=None):
        self.logger = logger
        self.device = self._setup_device(config.spade.device_type)
        self.bypass_spade = config.spade.bypass_spade
        self.colormap = config.spade.colormap
        
        if self.logger:
            self.logger.log(f"Using device: {self.device}")
        
        if not self.bypass_spade:
            self.model = self._initialize_model()
        else:
            self.model = None
        
    def _setup_device(self, device_type: str) -> torch.device:
        if device_type == 'auto':
            if torch.cuda.is_available():
                return torch.device('cuda')
            elif torch.backends.mps.is_available():
                return torch.device('mps')
            return torch.device('cpu')
        return torch.device(device_type)

    def _initialize_model(self) -> Pix2PixModel:
        project_root = get_project_root()
        checkpoints_dir = project_root / 'checkpoints'
    
        original_argv = sys.argv
        sys.argv = [sys.argv[0]]  
    
        opt = TestOptions().parse()
        opt.checkpoints_dir = str(checkpoints_dir)
        opt.name = 'tmpl'
        
        model = Pix2PixModel(opt)
        model.eval()
        model.to(self.device)
        
        sys.argv = original_argv
        return model
    
    def _colorize_mask(self, mask: np.ndarray) -> np.ndarray:
        min_val, max_val = np.min(mask), np.max(mask)
        
        mask_norm = np.zeros_like(mask, dtype=float) if min_val == max_val else (mask - min_val) / (max_val - min_val)
        colormap = plt.get_cmap(self.colormap)
        colored = colormap(mask_norm)
        
        return (colored[:, :, :3] * 255).astype(np.uint8)
        
    def process_mask(self, mask_path: Union[str, Path], output_path: Union[str, Path]) -> bool:
        try:
            if self.logger:
                self.logger.log(f"Processing mask: {mask_path}")

            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                if self.logger:
                    self.logger.log(f"Failed to load mask: {mask_path}")
                return False

            if self.bypass_spade:
                img = self._colorize_mask(mask)
            else:
                mask_tensor = torch.from_numpy(mask).unsqueeze(0).float().to(self.device)
                data = {
                    'label': mask_tensor.unsqueeze(0),
                    'instance': torch.zeros(1).to(self.device),
                    'image': torch.zeros(1, 3, mask.shape[0], mask.shape[1]).to(self.device)
                }

                with torch.no_grad():
                    if self.device.type == 'cuda':
                        with torch.cuda.amp.autocast():
                            generated = self.model(data, mode='inference')
                    else:
                        generated = self.model(data, mode='inference')

                img = ((generated[0].cpu().numpy() * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)
                if img.shape[0] == 3:
                    img = img.transpose(1, 2, 0)
    
                del generated, data
                if self.device.type == 'cuda':
                    torch.cuda.empty_cache()
                elif self.device.type == 'mps':
                    torch.mps.empty_cache()
 
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cv2.imwrite(str(output_path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), 
                       [cv2.IMWRITE_JPEG_QUALITY, 95])

            return True
            
        except Exception as e:
            if self.logger:
                self.logger.log(f"Error processing mask: {e}")
            return False