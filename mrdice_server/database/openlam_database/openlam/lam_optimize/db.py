import json
import logging
import os
from datetime import datetime
from typing import List, Optional

import requests
from pymatgen.core import Structure


class CrystalStructure:
    id: int
    formula: str
    structure: Structure
    energy: float
    submission_time: datetime
    provider: str
    def __init__(self, id: int, formula: str, structure: Structure, energy: float, submission_time: datetime, provider: str):
        self.id = id
        self.formula = formula
        self.structure = structure
        self.energy = energy
        self.submission_time = submission_time
        self.provider = provider

    @staticmethod
    def request_iterate(params: dict) -> dict:
        # ⚠️Warning: now we use a fixed access key for public database; in future, for private database, we will use the access key from the agent/user end
        access_key = os.environ.get("BOHRIUM_ACCESS_KEY", "242af226b70d4e0f9ef03ed28bfec095")
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

    @classmethod
    def query_by_offset(
        cls,
        formula: Optional[str] = None,
        min_energy: Optional[float] = None,
        max_energy: Optional[float] = None,
        min_submission_time: Optional[datetime] = None,
        max_submission_time: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 10,
    ) -> dict:
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

        data = cls.request_iterate(params)
        if data["items"] is not None:
            structures = []
            for item in data["items"]:
                structure = cls(id=item["id"], formula=item["formula"],
                                structure=Structure.from_dict(json.loads(item["structure"])),
                                energy=item["energy"],
                                submission_time=datetime.fromisoformat(item["submissionTime"]),
                                provider='openlam',
                                )
                structures.append(structure)
            data["items"] = structures
        return data

    @classmethod
    def query(
        cls,
        formula: Optional[str] = None,
        min_energy: Optional[float] = None,
        max_energy: Optional[float] = None,
        min_submission_time: Optional[datetime] = None,
        max_submission_time: Optional[datetime] = None,
    ) -> List["CrystalStructure"]:
        offset = 0
        structures = []
        while True:
            data = cls.query_by_offset(formula=formula, min_energy=min_energy, max_energy=max_energy,
                                       min_submission_time=min_submission_time, max_submission_time=max_submission_time, offset=offset)
            if data["items"] is None:
                break
            structures += data["items"]
            if data["nextStartId"] == 0:
                break
            offset = data["nextStartId"]
        return structures
