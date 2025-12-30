"""
Setup file for Apache Beam Dataflow pipeline.

This is required for Dataflow to install custom dependencies on workers.
"""

import setuptools

setuptools.setup(
    name="ecommerce-streaming-pipeline",
    version="1.0.0",
    description="E-commerce streaming pipeline for Pub/Sub to BigQuery ingestion",
    author="Data Engineering Team",
    packages=setuptools.find_packages(),
    install_requires=[
        "apache-beam[gcp]>=2.50.0",
    ],
    python_requires=">=3.9",
)
