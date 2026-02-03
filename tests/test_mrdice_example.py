"""
示例测试脚本：如何使用 test.yaml 测试 MrDice 接口

注意：这是一个示例脚本，实际测试需要根据 MCP 服务器的具体实现调整。
MCP 服务器使用 SSE (Server-Sent Events) 传输，可能需要使用专门的 MCP 客户端。
"""
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

def load_test_cases(json_file: str = "test.json") -> Dict[str, Any]:
    """加载测试用例配置"""
    # 从 tests 目录加载
    test_dir = Path(__file__).parent
    json_path = test_dir / json_file
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def test_mrdice_search_direct(query: str, n_results: int = 5, output_format: str = "cif"):
    """
    直接调用 mrdice_search 函数进行测试（需要导入模块）
    
    这是最直接的方式，适用于单元测试。
    """
    try:
        from mrdice_server.server import mrdice_search
        
        result = await mrdice_search(
            query=query,
            n_results=n_results,
            output_format=output_format,
        )
        return result
    except ImportError as e:
        print(f"无法导入 mrdice_server: {e}")
        print("请确保在项目根目录运行，并且已安装所有依赖")
        return None


def print_test_result(test_name: str, result: Dict[str, Any], expected: Dict[str, Any] = None):
    """打印测试结果"""
    print(f"\n{'='*60}")
    print(f"测试: {test_name}")
    print(f"{'='*60}")
    
    if result is None:
        print("❌ 测试失败: 无法获取结果")
        return False
    
    print(f"✅ 查询: {result.get('query_used', 'N/A')}")
    print(f"📊 找到结果数: {result.get('n_found', 0)}")
    print(f"📤 返回结果数: {result.get('returned', 0)}")
    print(f"📉 降级级别: {result.get('fallback_level', 0)}")
    
    results = result.get('results', [])
    if results:
        print(f"\n前 {min(3, len(results))} 个结果:")
        for i, r in enumerate(results[:3], 1):
            print(f"  {i}. {r.get('formula', 'N/A')} - {r.get('name', 'N/A')}")
            print(f"     来源: {r.get('source', 'N/A')}")
            if r.get('structure_file'):
                print(f"     结构文件: {r.get('structure_file')}")
    else:
        print("\n⚠️  未找到结果")
    
    # 验证期望值
    if expected:
        print(f"\n期望验证:")
        for key, value in expected.items():
            actual = result.get(key)
            if isinstance(value, str) and value.startswith(">"):
                # 处理 "> 0" 这样的条件
                threshold = int(value.split()[-1])
                if actual > threshold:
                    print(f"  ✅ {key}: {actual} {value}")
                else:
                    print(f"  ❌ {key}: {actual} 不满足 {value}")
            elif actual == value:
                print(f"  ✅ {key}: {actual}")
            else:
                print(f"  ❌ {key}: 期望 {value}, 实际 {actual}")
    
    return True


async def run_test_case(test_case: Dict[str, Any]):
    """运行单个测试用例"""
    name = test_case.get("name", "Unknown")
    params = test_case.get("parameters", {})
    expected = test_case.get("expected", {})
    
    query = params.get("query", "")
    n_results = params.get("n_results", 5)
    output_format = params.get("output_format", "cif")
    
    result = await test_mrdice_search_direct(query, n_results, output_format)
    print_test_result(name, result, expected)
    
    return result is not None


async def main():
    """主测试函数"""
    print("="*60)
    print("MrDice API 测试")
    print("="*60)
    
    # 加载测试配置
    try:
        config = load_test_cases("test.json")
    except FileNotFoundError:
        print("❌ 未找到 test.json 文件（应该在 tests/ 目录下）")
        return
    except Exception as e:
        print(f"❌ 加载测试配置失败: {e}")
        return
    
    test_cases = config.get("test_cases", [])
    test_config = config.get("test_config", {})
    
    print(f"\n📋 共 {len(test_cases)} 个测试用例")
    print(f"⚙️  测试配置: {json.dumps(test_config, indent=2, ensure_ascii=False)}")
    
    # 运行测试用例
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n[{i}/{len(test_cases)}] 运行测试用例...")
        success = await run_test_case(test_case)
        results.append(success)
        
        # 如果配置了不继续，遇到失败就停止
        if not test_config.get("continue_on_failure", True) and not success:
            print("\n⚠️  测试失败，停止执行")
            break
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    print(f"📊 成功率: {passed/total*100:.1f}%" if total > 0 else "N/A")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())

