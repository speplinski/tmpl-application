import depthai as dai
import time
import cv2
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from apps.depth_tracking.depth_tracker import DepthTracker
from apps.depth_tracking.visualizer import Visualizer
from apps.depth_tracking.column_analyzer import ColumnAnalyzer
from apps.generator.core.tmpl_monitor import TMPLMonitor
from apps.generator.configs.mask_config import MaskConfig
from apps.generator.utils.dynamic_config import get_project_root
from apps.generator.utils.diagnostic import InitializationDiagnostic
from integration.config.integrated_config import IntegratedConfig
from ..utils.console_logger import ConsoleLogger

class DepthMaskAdapter:
    def __init__(self, config: IntegratedConfig, logger=None):
        self.logger = logger or ConsoleLogger(name="DepthAdapter")
        self.config = config
        
        # Depth tracking components
        self.depth_tracker = DepthTracker(config)
        self.visualizer = Visualizer(config)
        self.column_analyzer = ColumnAnalyzer(config)
        
        # Camera components
        self.device: Optional[dai.Device] = None
        self.pipeline: Optional[dai.Pipeline] = None
        self.depth_queue: Optional[dai.DataOutputQueue] = None
        self.spatial_calc_queue: Optional[dai.DataOutputQueue] = None
        
        self._initialize_mask_system()

    def create_pipeline(self) -> dai.Pipeline:
        pipeline = dai.Pipeline()

        mono_left = pipeline.create(dai.node.MonoCamera)
        mono_right = pipeline.create(dai.node.MonoCamera)
        stereo = pipeline.create(dai.node.StereoDepth)
        spatial_calc = pipeline.create(dai.node.SpatialLocationCalculator)

        xout_depth = pipeline.create(dai.node.XLinkOut)
        xout_spatial = pipeline.create(dai.node.XLinkOut)
        xin_spatial_calc = pipeline.create(dai.node.XLinkIn)

        xout_depth.setStreamName("depth")
        xout_spatial.setStreamName("spatialData")
        xin_spatial_calc.setStreamName("spatialCalcConfig")

        mono_left.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_left.setCamera("left")
        mono_right.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
        mono_right.setCamera("right")

        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        stereo.setLeftRightCheck(True)
        stereo.setSubpixel(True)
        spatial_calc.inputConfig.setWaitForMessage(False)

        grid_h, grid_v = self.config.depth.grid_dimensions
        for y in range(grid_v):
            for x in range(grid_h):
                config = dai.SpatialLocationCalculatorConfigData()
                config.depthThresholds.lowerThreshold = 200
                config.depthThresholds.upperThreshold = 10000
                config.roi = dai.Rect(
                    dai.Point2f(x/grid_h, y/grid_v),
                    dai.Point2f((x+1)/grid_h, (y+1)/grid_v)
                )
                spatial_calc.initialConfig.addROI(config)

        mono_left.out.link(stereo.left)
        mono_right.out.link(stereo.right)
        spatial_calc.passthroughDepth.link(xout_depth.input)
        stereo.depth.link(spatial_calc.inputDepth)
        spatial_calc.out.link(xout_spatial.input)
        xin_spatial_calc.out.link(spatial_calc.inputConfig)

        return pipeline

    def _initialize_mask_system(self, panorama_id=None):
        try:
            diagnostic = InitializationDiagnostic()
            if not diagnostic.run_diagnostics():
                raise RuntimeError("Initialization diagnostic failed")

            project_root = get_project_root()
            mapping_path = project_root / 'data' / 'mask_mapping.json'
            
            with open(mapping_path) as f:
                mask_mappings = json.load(f)
                
            panorama_id = panorama_id or next(iter(mask_mappings.keys()))
            mapping = mask_mappings[panorama_id]
            
            all_masks = {**mapping['static_masks'], **mapping['sequence_masks']}
            mask_config = MaskConfig(
                name="depth_generated",
                gray_values=list(map(int, all_masks.keys())),
                gray_indexes={int(k): v for k, v in all_masks.items()}
            )
            
            self.tmpl_monitor = TMPLMonitor(
                panorama_id=panorama_id,
                mask_configs=[mask_config],
                logger=self.logger
            )

            self._initialize_masks()
            
        except Exception as e:
            self.logger.log(f"Error initializing mask system: {e}")
            raise

    def _initialize_masks(self):
        for name, manager in self.tmpl_monitor.mask_managers.items():
            manager.load_static_masks()
            
        total_frames = 0
        for name, manager in self.tmpl_monitor.mask_managers.items():
            frames = manager.scan_sequences()
            total_frames += frames
            
        self.logger.log(f"Total frames loaded: {total_frames}")

    def initialize(self) -> bool:
        try:
            self.pipeline = self.create_pipeline()
            self.device = dai.Device(self.pipeline)
            
            self.device.setIrLaserDotProjectorIntensity(0.5)
            self.depth_queue = self.device.getOutputQueue("depth", maxSize=4, blocking=False)
            self.spatial_calc_queue = self.device.getOutputQueue("spatialData", maxSize=4, blocking=False)
            
            return True
            
        except RuntimeError:
            self.logger.log("Error: Cannot access the OAK-D camera!")
            return False

    def update_config(self, config: IntegratedConfig):
        self.config = config
        self.depth_tracker.increment_interval = config.timing.counter_interval
        self.visualizer.config = config
        self.column_analyzer.config = config

    def process_frame(self) -> Tuple[Dict[str, Any], Optional[cv2.Mat]]:
        if not self.spatial_calc_queue or not self.depth_queue:
            raise RuntimeError("Device not initialized")

        spatial_data = self.spatial_calc_queue.get().getSpatialLocations()
        distances = [data.spatialCoordinates.z / 1000 for data in spatial_data]
        
        column_presence = self.column_analyzer.analyze_columns(
            distances, 
            self.config.depth.mirror_mode
        )
        self.depth_tracker.update(column_presence)
        counters = self.depth_tracker.position_counters
        
        if any(counters):
            self.tmpl_monitor.process_state(counters)
            
        stats = {
            "Mirror": "ON" if self.config.depth.mirror_mode else "OFF",
            "Columns": ",".join(map(str, column_presence)),
            "Counters": str(list(counters))
        }
        self.logger.update_stats(stats)

        heatmap = None
        if self.config.depth.display_window:
            heatmap = self.visualizer.create_heatmap(
                distances, 
                self.config.depth.mirror_mode
            )

        return {
            'distances': distances,
            'column_presence': column_presence,
            'counters': counters,
            'active_positions': list(self.depth_tracker.position_timers.keys()),
            'active_sequences': [(i, c) for i, c in enumerate(counters) if c > 0]
        }, heatmap

    def cleanup(self):
        if self.device:
            self.device.close()
            self.device = None