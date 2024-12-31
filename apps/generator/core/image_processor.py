from pathlib import Path
from typing import Optional, Dict
import cv2
import numpy as np

class ImageProcessor:
    """
    Handles image loading, resizing and processing operations.
    Maintains consistent dimensions and binary values across all operations.
    """
    
    # Target dimensions (height x width) for all processed images
    TARGET_SIZE = (1280, 3840)
    
    # Binary threshold value for mask processing
    BINARY_THRESHOLD = 127

    @staticmethod
    def load_and_resize_image(image_path: Path) -> Optional[np.ndarray]:
        """
        Load and resize image to standard dimensions while maintaining binary values.
        
        Args:
            image_path: Path to the image file (PNG or BMP)
            
        Returns:
            Optional[np.ndarray]: Binary image (values 0 and 255) at target dimensions,
                                or None if loading fails
        """
        # Load image in grayscale
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print(f"Failed to load image: {image_path}")
            return None
            
        # Convert to binary using threshold
        _, binary = cv2.threshold(image, 
                                ImageProcessor.BINARY_THRESHOLD, 
                                255, 
                                cv2.THRESH_BINARY)
        
        # Calculate scaling to match target width
        current_h, current_w = binary.shape
        scale = ImageProcessor.TARGET_SIZE[1] / current_w
        new_h = int(current_h * scale)
        
        # Resize image using nearest neighbor to maintain binary values
        resized = cv2.resize(binary, 
                           (ImageProcessor.TARGET_SIZE[1], new_h),
                           interpolation=cv2.INTER_NEAREST)
        
        # Handle height adjustment
        if new_h > ImageProcessor.TARGET_SIZE[0]:
            # Crop center if too tall
            start = (new_h - ImageProcessor.TARGET_SIZE[0]) // 2
            resized = resized[start:start + ImageProcessor.TARGET_SIZE[0], :]
        elif new_h < ImageProcessor.TARGET_SIZE[0]:
            # Pad with zeros if too short
            pad_top = (ImageProcessor.TARGET_SIZE[0] - new_h) // 2
            pad_bottom = ImageProcessor.TARGET_SIZE[0] - new_h - pad_top
            resized = np.pad(resized, 
                           ((pad_top, pad_bottom), (0, 0)),
                           mode='constant')

        # Final binary threshold to ensure only 0 and 255 values
        _, final = cv2.threshold(resized,
                               ImageProcessor.BINARY_THRESHOLD,
                               255,
                               cv2.THRESH_BINARY)
                               
        # Verify final dimensions
        if final.shape != ImageProcessor.TARGET_SIZE:
            print(f"Warning: Incorrect final dimensions {final.shape}")
            return None
            
        # Verify binary values
        unique_values = np.unique(final)
        if not all(val in [0, 255] for val in unique_values):
            print(f"Warning: Non-binary values present {unique_values}")
            return None
            
        return final

    @staticmethod
    def combine_masks(masks: Dict[int, np.ndarray], gray_indexes: Dict[int, int]) -> np.ndarray:
        """
        Combine multiple masks into single output image with proper indexes.
        
        Args:
            masks: Dictionary mapping gray values to their corresponding binary masks
            gray_indexes: Mapping from gray values to final index values
            
        Returns:
            np.ndarray: Combined mask with indexed values
        """
        # Create output array with background value (255)
        combined_image = np.full(ImageProcessor.TARGET_SIZE, 255, dtype=np.uint8)
        
        print("\nCombining masks:")
        for gray_value, mask in masks.items():
            if gray_value not in gray_indexes:
                print(f"Warning: No index mapping for gray value {gray_value}")
                continue
                
            # Verify mask dimensions
            if mask.shape != ImageProcessor.TARGET_SIZE:
                print(f"Warning: Incorrect mask dimensions for {gray_value}: {mask.shape}")
                continue
            
            # Verify binary values
            unique_values = np.unique(mask)
            print(f"Gray value {gray_value} mask unique values: {unique_values}")
            if not all(val in [0, 255] for val in unique_values):
                print(f"Warning: Non-binary values in mask {gray_value}")
                continue
            
            # Apply index to mask
            index = gray_indexes[gray_value]
            pixels_to_set = np.sum(mask > 0)
            combined_image[mask > 0] = index
            pixels_set = np.sum(combined_image == index)
            print(f"Set {pixels_set} pixels for gray value {gray_value} to index {index}")
        
        return combined_image