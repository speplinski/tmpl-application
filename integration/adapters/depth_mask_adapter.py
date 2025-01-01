import depthai as dai
import time
import cv2
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from apps.depth_tracking.config import Config
from apps.depth_tracking.depth_tracker import DepthTracker
from apps.depth_tracking.visualizer import Visualizer
from apps.depth_tracking.column_analyzer import ColumnAnalyzer
from apps.generator.core.tmpl_monitor import TMPLMonitor
from apps.generator.configs.mask_config import MaskConfig
from apps.generator.utils.dynamic_config import get_project_root
from apps.generator.utils.diagnostic import InitializationDiagnostic
from ..utils.console_logger import ConsoleLogger


class DepthMaskAdapter:
    """
    Adapter that manages OAK-D camera pipeline and depth tracking functionality,
    integrated with mask generation system.
    """
    def __init__(self):
        # Depth tracking components
        self.config = Config()
        self.depth_tracker = DepthTracker()
        self.visualizer = Visualizer(self.config)
        self.column_analyzer = ColumnAnalyzer(self.config)
        
        # Logger setup
        self.logger = ConsoleLogger()
        
        # Camera components
        self.device: Optional[dai.Device] = None
        self.pipeline: Optional[dai.Pipeline] = None
        self.depth_queue: Optional[dai.DataOutputQueue] = None
        self.spatial_calc_queue: Optional[dai.DataOutputQueue] = None
        
        # Mask system components
        self._initialize_mask_system()

    def _initialize_mask_system(self):
        """Initialize mask system configuration"""
        try:
            diagnostic = InitializationDiagnostic()
            if not diagnostic.run_diagnostics():
                raise RuntimeError("Initialization diagnostic failed")
        
            # Get project root and mapping file path
            project_root = get_project_root()
            mapping_path = project_root / 'data' / 'mask_mapping.json'
            self.logger.log(f"Looking for mapping file at: {mapping_path}")
            
            if not mapping_path.exists():
                raise FileNotFoundError(f"Mapping file not found at: {mapping_path}")
                
            # Load mask mapping
            with open(mapping_path) as f:
                mask_mappings = json.load(f)
                
            # Create mask config from first panorama
            panorama_id = next(iter(mask_mappings.keys()))
            mapping = mask_mappings[panorama_id]
            
            # Combine static and sequence masks
            all_masks = {**mapping['static_masks'], **mapping['sequence_masks']}
            mask_config = MaskConfig(
                name="depth_generated",
                gray_values=list(map(int, all_masks.keys())),
                gray_indexes={int(k): v for k, v in all_masks.items()}
            )
            
            # Initialize monitor with our config
            self.tmpl_monitor = TMPLMonitor(
                panorama_id=panorama_id,
                mask_configs=[mask_config],
                logger=self.logger  # Pass our logger
            )

            self._initialize_masks()
            
            self.logger.log(f"Mask system initialized: {panorama_id}")
            self.logger.log(f"Gray values/indexes: {mask_config.gray_indexes}")
            
        except Exception as e:
            self.logger.log(f"Error initializing mask system: {e}")
            raise

    def _initialize_masks(self):
        """Initialize and load all masks"""
        self.logger.log("Loading masks...")
        
        for name, manager in self.tmpl_monitor.mask_managers.items():
            self.logger.log(f"Loading static masks for {name}")
            manager.load_static_masks()
            
        self.logger.log("Loading sequence frames...")
        total_frames = 0
        for name, manager in self.tmpl_monitor.mask_managers.items():
            frames = manager.load_sequence_frames()
            total_frames += frames
            self.logger.log(f"Loaded {frames} frames for {name}")
            
        self.logger.log(f"Total frames loaded: {total_frames}")

    def create_pipeline(self) -> dai.Pipeline:
        """Create and configure the OAK-D pipeline."""
        pipeline = dai.Pipeline()

        # Define sources and outputs
        mono_left = pipeline.create(dai.node.MonoCamera)
        mono_right = pipeline.create(dai.node.MonoCamera)
        stereo = pipeline.create(dai.node.StereoDepth)
        spatial_calc = pipeline.create(dai.node.SpatialLocationCalculator)

        xout_depth = pipeline.create(dai.node.XLinkOut)
        xout_spatial = pipeline.create(dai.node.XLinkOut)
        xin_spatial_calc = pipeline.create(dai.node.XLinkIn)

        # Set stream names
        xout_depth.setStreamName("depth")
        xout_spatial.setStreamName("spatialData")
        xin_spatial_calc.setStreamName("spatialCalcConfig")

        # Configure cameras
        mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_left.setCamera("left")
        mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_right.setCamera("right")

        # Configure stereo depth
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setLeftRightCheck(True)
        stereo.setSubpixel(True)
        spatial_calc.inputConfig.setWaitForMessage(False)

        # Configure ROIs for spatial calculator
        for y in range(self.config.nV):
            for x in range(self.config.nH):
                config = dai.SpatialLocationCalculatorConfigData()
                config.depthThresholds.lowerThreshold = 200
                config.depthThresholds.upperThreshold = 10000
                config.roi = dai.Rect(
                    dai.Point2f(x/self.config.nH, y/self.config.nV),
                    dai.Point2f((x+1)/self.config.nH, (y+1)/self.config.nV)
                )
                spatial_calc.initialConfig.addROI(config)

        # Link nodes
        mono_left.out.link(stereo.left)
        mono_right.out.link(stereo.right)
        spatial_calc.passthroughDepth.link(xout_depth.input)
        stereo.depth.link(spatial_calc.inputDepth)
        spatial_calc.out.link(xout_spatial.input)
        xin_spatial_calc.out.link(spatial_calc.inputConfig)

        return pipeline

    def initialize(self) -> bool:
        """Initialize the OAK-D device and pipeline."""
        try:
            self.logger.log("Initializing OAK-D camera...")
            self.pipeline = self.create_pipeline()
            self.logger.log("Pipeline created successfully")
            self.device = dai.Device(self.pipeline)
            self.logger.log("Device initialized successfully")
            
            # Set up device and queues
            self.device.setIrLaserDotProjectorIntensity(0.5)
            self.depth_queue = self.device.getOutputQueue("depth", maxSize=4, blocking=False)
            self.spatial_calc_queue = self.device.getOutputQueue("spatialData", maxSize=4, blocking=False)
            
            return True
            
        except RuntimeError:
            self.logger.log("Error: Cannot access the OAK-D camera!")
            self.logger.log("Please check if another application is using the camera")
            self.logger.log("or try reconnecting the device.")
            return False

    def process_frame(self) -> Tuple[Dict[str, Any], Optional[cv2.Mat]]:
        """Process a single frame and update mask system."""
        if not self.spatial_calc_queue or not self.depth_queue:
            raise RuntimeError("Device not initialized")

        # Get depth data
        spatial_data = self.spatial_calc_queue.get().getSpatialLocations()
        distances = [data.spatialCoordinates.z / 1000 for data in spatial_data]
        
        # Process depth data
        column_presence = self.column_analyzer.analyze_columns(distances, self.config.MIRROR_MODE)
        self.depth_tracker.update(column_presence)

        # Get current counters for mask system
        counters = self.depth_tracker.position_counters

        # Update console stats
        stats = {
            "Mirror": "ON" if self.config.MIRROR_MODE else "OFF",
            "Columns": ",".join(map(str, column_presence)),
            "Counters": str(list(counters))
        }
        self.logger.update_stats(stats)

        # Process masks if there are active positions
        active_sequences = []
        for i, count in enumerate(counters):
            if count > 0:
                frame_num = min(count, 10)  # Limit to max 10 frames
                active_sequences.append((i, frame_num))

        if active_sequences:
            try:
                self.tmpl_monitor.process_state(counters)
            except Exception as e:
                self.logger.log(f"Error processing mask: {e}")

        # Create visualization if enabled
        heatmap = None
        if self.config.DISPLAY_WINDOW:
            heatmap = self.visualizer.create_heatmap(distances, self.config.MIRROR_MODE)

        return {
            'distances': distances,
            'column_presence': column_presence,
            'counters': counters,
            'active_positions': list(self.depth_tracker.position_timers.keys()),
            'active_sequences': active_sequences
        }, heatmap

    def cleanup(self):
        """Clean up resources."""
        if self.device:
            self.device.close()
            self.device = None