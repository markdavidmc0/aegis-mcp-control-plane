#!/usr/bin/env python3
"""Vortex ASIC/CPU Tensor Kernel Profiling Executable.

Executes real matrix multiplication benchmarks across specified dimensions and data types,
measuring actual execution latency, memory footprint, achieved FLOPS, and operational intensity.
"""

import argparse
import json
import sys
import time

import numpy as np


def benchmark_gemm(
    matrix_dim: int,
    data_type: str = "float32",
    warmup_runs: int = 2,
    iterations: int = 5,
) -> dict:
    """Executes a matrix multiplication benchmark and calculates hardware metrics."""
    dtype_map = {
        "float32": np.float32,
        "float16": np.float16,
        "float64": np.float64,
        "int8": np.int8,
    }

    np_dtype = dtype_map.get(data_type.lower())
    if np_dtype is None:
        return {
            "status": "FAILED",
            "error": f"Unsupported data type '{data_type}'. Supported: {list(dtype_map.keys())}",
        }

    try:
        # Allocate matrices mat_a and mat_b
        mat_a = np.random.randn(matrix_dim, matrix_dim).astype(np_dtype)
        mat_b = np.random.randn(matrix_dim, matrix_dim).astype(np_dtype)
    except Exception as e:
        return {
            "status": "FAILED",
            "error": f"Allocation failed for dim={matrix_dim}, dtype={data_type}: {e}",
        }

    # Warmup runs to prime CPU L1/L2 caches and BLAS threads
    for _ in range(warmup_runs):
        _ = mat_a @ mat_b

    # Benchmark loop measuring wall-clock time
    start_ns = time.perf_counter_ns()
    for _ in range(iterations):
        _ = mat_a @ mat_b
    end_ns = time.perf_counter_ns()

    total_elapsed_sec = (end_ns - start_ns) / 1e9
    avg_latency_ms = (total_elapsed_sec / iterations) * 1000.0

    # Total FLOPS for N x N GEMM: 2 * N^3 operations per multiplication
    ops_per_iter = 2 * (matrix_dim**3)
    total_ops = ops_per_iter * iterations
    achieved_gflops = (total_ops / total_elapsed_sec) / 1e9

    # Memory footprint calculation (A, B, and result matrix C)
    bytes_per_elem = np.dtype(np_dtype).itemsize
    memory_mb = (3 * (matrix_dim**2) * bytes_per_elem) / (1024 * 1024)

    # Arithmetic intensity: FLOPs / Byte transferred
    bytes_transferred = 3 * (matrix_dim**2) * bytes_per_elem
    arithmetic_intensity = ops_per_iter / bytes_transferred
    bottleneck = "MEMORY_BOUND" if arithmetic_intensity < 8.0 else "COMPUTE_BOUND"

    return {
        "matrix_dim": matrix_dim,
        "data_type": data_type,
        "iterations": iterations,
        "avg_latency_ms": round(avg_latency_ms, 3),
        "achieved_gflops": round(achieved_gflops, 2),
        "ops_per_gemm": ops_per_iter,
        "memory_footprint_mb": round(memory_mb, 2),
        "arithmetic_intensity": round(arithmetic_intensity, 2),
        "bottleneck_classification": bottleneck,
        "status": "SUCCESS",
    }


def main():
    """Main CLI entrypoint for tensor kernel profiling."""
    parser = argparse.ArgumentParser(description="Tensor Kernel Profiler")
    parser.add_argument("--json-args", type=str, required=True, help="JSON arguments payload")
    args = parser.parse_args()

    try:
        parsed_args = json.loads(args.json_args)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "FAILED", "error": f"Invalid JSON payload: {e}"}))
        sys.exit(1)

    matrix_dim = int(parsed_args.get("matrix_dim", 512))
    data_type = str(parsed_args.get("data_type", "float32"))
    iterations = int(parsed_args.get("iterations", 5))

    metrics = benchmark_gemm(
        matrix_dim=matrix_dim,
        data_type=data_type,
        iterations=iterations,
    )

    # Emit JSON payload directly to stdout for Data Plane capture
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
