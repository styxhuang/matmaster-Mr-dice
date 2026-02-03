class Tool:
    def __init__(self, name):
        self.name = name

import math

def photo_consume_calculate(tool, args):
    """
    Mr. Dice 系列数据库工具的光子收费

    :param tool: 工具对象（必须有 name 属性）
    :param args: 工具调用参数（需要 n_results）
    :return: (final_cost_rmb, final_cost_photons)
    """
    tool_name = getattr(tool, "name", None)
    if not tool_name:
        raise ValueError("Tool name not found")

    n_results = int(args.get("n_results", 1))  # 默认返回 1 条

    # 工具映射到计费系列
    optimade_tools = {
        "fetch_structures_with_filter",
        "fetch_structures_with_spg",
        "fetch_structures_with_bandgap",
    }
    bohrium_tools = {"fetch_bohrium_crystals"}
    openlam_tools = {"fetch_openlam_structures"}

    pricing_rules = {
        "optimade": {"base": 0.088, "per_item": 0.0088},
        "bohriumpublic": {"base": 0.068, "per_item": 0.0068},
        "openlam": {"base": 0.058, "per_item": 0.0058},
    }

    if tool_name in optimade_tools:
        rule = pricing_rules["optimade"]
    elif tool_name in bohrium_tools:
        rule = pricing_rules["bohriumpublic"]
    elif tool_name in openlam_tools:
        rule = pricing_rules["openlam"]
    else:
        raise ValueError(f"Unsupported tool for pricing: {tool_name}")

    # RMB 成本
    final_cost_rmb = rule["base"] + n_results * rule["per_item"]

    # 转换为光子，1 光子 = ¥0.01，向上取整
    final_cost_photons = math.ceil(final_cost_rmb / 0.01)

    print(f"[Pricing] Tool={tool_name}, n_results={n_results}")
    print(f"[Pricing] Cost=¥{final_cost_rmb:.4f} ≈ {final_cost_photons} photons")

    return final_cost_rmb, final_cost_photons

def run_tests():
    test_cases = [
        # Optimade 系列
        (Tool("fetch_structures_with_filter"), {"n_results": 1}),
        (Tool("fetch_structures_with_spg"), {"n_results": 10}),
        (Tool("fetch_structures_with_bandgap"), {"n_results": 50}),
        
        # Bohrium 系列
        (Tool("fetch_bohrium_crystals"), {"n_results": 1}),
        (Tool("fetch_bohrium_crystals"), {"n_results": 10}),
        (Tool("fetch_bohrium_crystals"), {"n_results": 50}),
        
        # OpenLAM 系列
        (Tool("fetch_openlam_structures"), {"n_results": 1}),
        (Tool("fetch_openlam_structures"), {"n_results": 10}),
        (Tool("fetch_openlam_structures"), {"n_results": 50}),
    ]

    for tool, args in test_cases:
        print("=" * 50)
        try:
            rmb, photons = photo_consume_calculate(tool, args)
            print(f"Tool: {tool.name}, n_results={args['n_results']}")
            print(f"→ RMB: {rmb:.4f}, Photons: {photons}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_tests()