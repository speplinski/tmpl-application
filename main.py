import argparse
import sys
from integration.config import IntegratedConfig
from integration.core import IntegratedDisplay

def parse_arguments():
    parser = argparse.ArgumentParser(description='Integrated TMPL Application')
    parser.add_argument('--monitor', type=int, default=1,
                       help='Monitor index (0 is usually the main display)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug mode')
    parser.add_argument('--no-visualization', action='store_true',
                       help='Disable depth visualization')
    parser.add_argument('--mirror', action='store_true',
                       help='Enable mirror mode')
    return parser.parse_args()

def main():
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Create and configure the system
        config = IntegratedConfig()
        config.debug_mode = args.debug
        config.show_visualization = not args.no_visualization
        config.mirror_mode = args.mirror
        
        # Initialize integrated display system
        display = IntegratedDisplay(config, monitor_index=args.monitor)
        
        # Run the application
        display.run()
        
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
        if config.debug_mode:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()