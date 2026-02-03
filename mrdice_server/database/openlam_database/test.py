import json
from lam_optimize.utils import query_hull_by_composition
from lam_optimize import CrystalStructure
from dotenv import load_dotenv

load_dotenv()

# hull = query_hull_by_composition(["Ac", "Ag", "Bi", "As", "Rh", "Cl", "O"])
# print(hull)
# pass


data = CrystalStructure.query_by_offset(formula="Fe2O3", limit=2)

# 将CrystalStructure对象转换为可序列化的字典
def crystal_structure_to_dict(crystal_structure):
    """将CrystalStructure对象转换为字典"""
    return {
        "formula": crystal_structure.formula,
        "energy": crystal_structure.energy,
        "submission_time": crystal_structure.submission_time.isoformat(),
        "structure": crystal_structure.structure.as_dict()
    }

# 转换数据结构
if data["items"] is not None:
    serializable_data = {
        "total": data.get("total", 0),
        "nextStartId": data.get("nextStartId", 0),
        "items": [crystal_structure_to_dict(item) for item in data["items"]]
    }
else:
    serializable_data = {
        "total": data.get("total", 0),
        "nextStartId": data.get("nextStartId", 0),
        "items": []
    }

# 以JSON格式打印结果
print(json.dumps(serializable_data, indent=2, ensure_ascii=False))

# 保存到JSON文件
output_filename = "fe2o3_structures.json"
with open(output_filename, 'w', encoding='utf-8') as f:
    json.dump(serializable_data, f, indent=2, ensure_ascii=False)

print(f"\n数据已保存到文件: {output_filename}")