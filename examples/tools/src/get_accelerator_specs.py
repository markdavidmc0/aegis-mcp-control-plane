#!/usr/bin/env python3
"""Vortex ASIC Hardware Specifications Tool Executable."""

import argparse
import json
import sys


def get_specs(architecture: str) -> dict:
    """Returns hardware spec limits and Roofline ridge points for target chips."""
    architectures = {
        "vortex-npu-v2": {
            "architecture": "vortex-npu-v2",
            "peak_tflops": 128.0,
            "memory_bandwidth_gbs": 1024.0,
            "ridge_point": 125.0,  # 128 TFLOPS / 1.024 TB/s
            "vector_unit_bits": 512,
            "status": "ACTIVE",
        },
        "vortex-edge-v1": {
            "architecture": "vortex-edge-v1",
            "peak_tflops": 32.0,
            "memory_bandwidth_gbs": 256.0,
            "ridge_point": 125.0,
            "vector_unit_bits": 256,
            "status": "ACTIVE",
        },
    }

    arch_key = architecture.lower()
    if arch_key in architectures:
        return architectures[arch_key]

    return {
        "architecture": architecture,
        "peak_tflops": 64.0,
        "memory_bandwidth_gbs": 512.0,
        "ridge_point": 125.0,
        "vector_unit_bits": 256,
        "status": "DEFAULT_ESTIMATE",
    }


def main():
    """Main CLI entrypoint for accelerator specs profiling."""
    parser = argparse.ArgumentParser(description="Accelerator Specs Profiler")
    parser.add_argument("--json-args", type=str, required=True, help="JSON arguments payload")
    args = parser.parse_args()

    try:
        parsed_args = json.loads(args.json_args)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "FAILED", "error": f"Invalid JSON payload: {e}"}))
        sys.exit(1)

    architecture = str(parsed_args.get("architecture", "vortex-npu-v2"))
    specs = get_specs(architecture)
    print(json.dumps(specs))


if __name__ == "__main__":
    main()
