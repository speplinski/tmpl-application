import os
import psutil

class SystemMonitor:
    @staticmethod
    def get_memory_usage() -> float:
        """Returns memory usage in MB"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info().rss
        return memory_info / 1024 / 1024

    @staticmethod
    def print_memory_status():
        """Prints current memory status"""
        memory_mb = SystemMonitor.get_memory_usage()
        total_memory = psutil.virtual_memory().total / 1024 / 1024
        print(f"Memory usage: {memory_mb:.1f} MB")
        print(f"Total system memory: {total_memory:.1f} MB")
        print(f"Memory usage percentage: {(memory_mb/total_memory)*100:.1f}%")