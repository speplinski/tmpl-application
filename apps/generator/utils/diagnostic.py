import os
from pathlib import Path
import json
from typing import Dict, Optional

class InitializationDiagnostic:
    """Diagnostic tool for checking mask system initialization"""
    
    def __init__(self):
        self.issues = []
        
    def check_project_structure(self, root_path: Path) -> bool:
        """Verify the project structure exists correctly"""
        required_paths = [
            root_path / 'data' / 'landscapes',
            root_path / 'data' / 'mask_mapping.json'
        ]
        
        for path in required_paths:
            if not path.exists():
                self.issues.append(f"Missing required path: {path}")
                return False
        return True
        
    def validate_mask_mapping(self, mapping_path: Path) -> Optional[Dict]:
        """Validate the mask mapping configuration"""
        try:
            with open(mapping_path) as f:
                mapping = json.load(f)
                
            # Verify structure
            if not isinstance(mapping, dict):
                self.issues.append("Mask mapping must be a dictionary")
                return None
                
            for panorama_id, config in mapping.items():
                if not isinstance(config, dict):
                    self.issues.append(f"Invalid configuration for panorama {panorama_id}")
                    continue
                    
                required_keys = ['static_masks', 'sequence_masks']
                for key in required_keys:
                    if key not in config:
                        self.issues.append(f"Missing {key} in configuration for {panorama_id}")
                        return None
                        
                # Validate mask values
                for mask_type in ['static_masks', 'sequence_masks']:
                    masks = config[mask_type]
                    if not isinstance(masks, dict):
                        self.issues.append(f"Invalid {mask_type} format for {panorama_id}")
                        continue
                        
                    for gray_val, index in masks.items():
                        try:
                            int(gray_val)
                            int(index)
                        except ValueError:
                            self.issues.append(f"Invalid value in {mask_type}: {gray_val} -> {index}")
                            
            return mapping
        except json.JSONDecodeError:
            self.issues.append(f"Invalid JSON in mask mapping file: {mapping_path}")
            return None
        except Exception as e:
            self.issues.append(f"Error reading mask mapping: {str(e)}")
            return None
            
    def check_panorama_files(self, landscapes_dir: Path, panorama_id: str, mapping: Dict) -> bool:
        """Verify panorama files exist as specified in mapping"""
        panorama_dir = landscapes_dir / panorama_id
        if not panorama_dir.exists():
            self.issues.append(f"Panorama directory not found: {panorama_dir}")
            return False
            
        # Check static masks
        for gray_val in mapping[panorama_id]['static_masks']:
            mask_file = panorama_dir / f"{panorama_id}_{gray_val}.png"
            if not mask_file.exists():
                self.issues.append(f"Missing static mask file: {mask_file}")
                
        # Check sequence directories
        for gray_val in mapping[panorama_id]['sequence_masks']:
            seq_dir = panorama_dir / f"{panorama_id}_{gray_val}"
            if not seq_dir.exists():
                self.issues.append(f"Missing sequence directory: {seq_dir}")
                
        return len(self.issues) == 0
        
    def run_diagnostics(self, root_path: Optional[Path] = None) -> bool:
        """Run all diagnostic checks"""
        if root_path is None:
            from apps.generator.utils.dynamic_config import get_project_root
            try:
                root_path = get_project_root()
            except RuntimeError as e:
                print(f"\nError finding project root: {e}")
                return False
                
        print(f"\nRunning initialization diagnostics from: {root_path}")
        
        # Check basic structure
        if not self.check_project_structure(root_path):
            print("❌ Project structure check failed")
            return False
            
        # Validate mapping file
        mapping_path = root_path / 'data' / 'mask_mapping.json'
        mapping = self.validate_mask_mapping(mapping_path)
        if mapping is None:
            print("❌ Mask mapping validation failed")
            return False
            
        # Check panorama files
        landscapes_dir = root_path / 'data' / 'landscapes'
        all_valid = True
        for panorama_id in mapping:
            if not self.check_panorama_files(landscapes_dir, panorama_id, mapping):
                all_valid = False
                
        if not all_valid:
            print("❌ Panorama files check failed")
            
        # Print all issues
        if self.issues:
            print("\nFound the following issues:")
            for issue in self.issues:
                print(f"  - {issue}")
            return False
            
        print("✅ All initialization checks passed")
        return True