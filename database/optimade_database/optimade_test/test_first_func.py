#!/usr/bin/env python3
"""
Simple test for the first function: fetch_structures_with_filter
"""
import asyncio
import logging
from server import fetch_structures_with_filter

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_basic_filter():
    """Test with a simple filter"""
    print("Testing fetch_structures_with_filter with simple filter...")
    
    # Simple filter for silicon oxide
    result = await fetch_structures_with_filter(
        filter='chemical_formula_reduced="O2Si"',
        as_format="cif",
        n_results=1,
        providers=["mp", "cod"]  # Just test with 2 providers
    )
    
    print(f"Result: {result}")
    if result["output_dir"].exists():
        print(f"Output directory created: {result['output_dir']}")
        files = list(result["output_dir"].glob("*"))
        print(f"Files created: {[f.name for f in files]}")
    else:
        print("No output directory created")

if __name__ == "__main__":
    asyncio.run(test_basic_filter())
