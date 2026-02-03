import os
import json
import requests
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def request_iterate(params: dict) -> dict:
    access_key = os.environ.get("BOHRIUM_ACCESS_KEY")
    query_url = os.environ.get("OPENLAM_STRUCTURE_QUERY_URL", "http://openapi.dp.tech/openapi/v1/structures/iterate")
    headers = {
        "Content-type": "application/json",
    }
    params["accessKey"] = access_key
    rsp = requests.get(query_url, headers=headers, params=params)
    if rsp.status_code != 200:
        raise RuntimeError("Response code %s: %s" % (rsp.status_code, rsp.text))
    res = json.loads(rsp.text)
    if res["code"] != 0:
        raise RuntimeError("Query error code %s: %s" % (res["code"], res["error"]["msg"]))
    data = res["data"]
    return data


def query_structures(
    formula: Optional[str] = None,
    min_energy: Optional[float] = None,
    max_energy: Optional[float] = None,
    min_submission_time: Optional[datetime] = None,
    max_submission_time: Optional[datetime] = None,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """Query structures from OpenLAM database with optional filters"""
    params = {
        "startId": offset,
        "limit": limit,
    }
    if formula is not None:
        params["formula"] = formula
    if min_energy is not None:
        params["minEnergy"] = min_energy
    if max_energy is not None:
        params["maxEnergy"] = max_energy
    if min_submission_time is not None:
        params["minSubmissionTime"] = min_submission_time.isoformat()
    if max_submission_time is not None:
        params["maxSubmissionTime"] = max_submission_time.isoformat()
    
    data = request_iterate(params)
    if data["items"] is not None:
        structures = []
        for item in data["items"]:
            structure = cls(formula=item["formula"],
                            structure=Structure.from_dict(json.loads(item["structure"])),
                            energy=item["energy"],
                            submission_time=datetime.fromisoformat(item["submissionTime"]))
            structures.append(structure)
        data["items"] = structures
    return data


def main():
    """Simple demo of the OpenLAM API"""
    print("OpenLAM Database API Demo")
    print("=" * 30)
    
    try:
        # # Demo 1: Basic query
        # print("1. Basic query (get 3 structures):")
        # result = query_structures(limit=3)
        # items = result.get('items', [])
        # print(f"   Found {len(items)} structures")
        
        # Demo 2: Query by formula
        print("\n2. Query by formula (Fe2O3):")
        result = query_structures(formula="Fe2O3", limit=2)
        items = result.get('items', [])
        print(f"   Found {len(items)} Fe2O3 structures")
        
        # # Demo 3: Query with energy filter
        # print("\n3. Query with energy filter:")
        # result = query_structures(min_energy=-100.0, max_energy=0.0, limit=2)
        # items = result.get('items', [])
        # print(f"   Found {len(items)} structures in energy range")
        
        print("\n✓ Demo completed successfully!")
        
    except Exception as e:
        print(f"✗ Demo failed: {e}")


if __name__ == "__main__":
    main()