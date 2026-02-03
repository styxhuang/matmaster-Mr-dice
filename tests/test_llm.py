"""
简单的 LLM 测试脚本 - 直接测试 API 连接
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# 加载环境变量
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


def get_llm_config():
    """获取 LLM 配置"""
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
    api_base = os.getenv("LLM_API_BASE", "").strip() or None
    api_key = os.getenv("LLM_API_KEY", "").strip() or None
    
    # 解析 API base（不做容错，必须显式配置）
    if not api_base:
        raise ValueError("LLM_API_BASE is not set")
    api_base = api_base.rstrip("/")
    
    return {
        "provider": provider,
        "model": model,
        "api_base": api_base,
        "api_key": api_key,
    }


def test_llm_config():
    """测试 LLM 配置"""
    print("=" * 60)
    print("测试 LLM 配置")
    print("=" * 60)
    
    try:
        config = get_llm_config()
        print(f"Provider: {config['provider']}")
        print(f"Model: {config['model']}")
        print(f"API Base: {config['api_base']}")
        print(f"API Key: {'已设置 ✅' if config['api_key'] else '❌ 未设置'}")
        
        if not config['api_key']:
            print("\n⚠️  警告: LLM_API_KEY 未设置")
            print("   请在 .env 文件中设置: LLM_API_KEY=your_api_key_here")
            return False, None
        
        return True, config
    except Exception as e:
        print(f"❌ 配置错误: {e}")
        return False, None


def test_llm_connection(config):
    """测试 LLM 连接"""
    print("\n" + "=" * 60)
    print("测试 LLM 连接")
    print("=" * 60)
    
    try:
        url = f"{config['api_base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
                {"role": "user", "content": "Say 'Hello, LLM is working!' if you can read this."},
            ],
            "temperature": 0.2,
        }
        
        print(f"发送请求到: {url}")
        print(f"Model: {config['model']}")
        print("等待响应...")
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        print(f"\n✅ LLM 响应成功!")
        print(f"响应内容: {content}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 网络请求失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"错误详情: {error_data}")
            except:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应内容: {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_preprocessing_simple(config):
    """测试预处理功能（简化版）"""
    print("\n" + "=" * 60)
    print("测试预处理功能（意图识别）")
    print("=" * 60)
    
    try:
        url = f"{config['api_base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        
        system_prompt = "You are a material database search assistant. Return strict JSON only."
        user_prompt = """Input Query: 找一些 Fe2O3 材料

Return JSON:
{
  "material_type": "crystal|mof|unknown",
  "domain": "semiconductor|catalyst|battery|perovskite|zeolite|other",
  "confidence": 0.0-1.0
}"""
        
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        
        print(f"查询: 找一些 Fe2O3 材料")
        print("正在使用 LLM 进行意图识别...")
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        print('content: ', content)
        # 尝试解析 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group(0))
            print(f"\n✅ 预处理成功!")
            print(f"材料类型: {result.get('material_type', 'N/A')}")
            print(f"领域: {result.get('domain', 'N/A')}")
            print(f"置信度: {result.get('confidence', 'N/A')}")
            return True
        else:
            print(f"\n⚠️  响应格式异常: {content[:100]}")
            return False
            
    except Exception as e:
        print(f"\n❌ 预处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("MrDice LLM 接入测试")
    print("=" * 60)
    
    results = []
    
    # 测试 1: 配置检查
    print("\n[1/3] 检查配置...")
    config_ok, config = test_llm_config()
    results.append(("配置检查", config_ok))
    
    # 如果配置有问题，直接返回
    if not config_ok:
        print("\n" + "=" * 60)
        print("❌ 配置检查失败，请先配置 LLM_API_KEY")
        print("=" * 60)
        print("\n请在 .env 文件中设置:")
        print("  LLM_PROVIDER=deepseek")
        print("  LLM_MODEL=deepseek/deepseek-chat")
        print("  LLM_API_KEY=your_api_key_here")
        return
    
    # 测试 2: LLM 连接
    print("\n[2/3] 测试 LLM 连接...")
    results.append(("LLM 连接", test_llm_connection(config)))
    
    # 测试 3: 预处理
    if results[-1][1]:  # 如果连接成功
        print("\n[3/3] 测试预处理功能...")
        results.append(("预处理功能", test_preprocessing_simple(config)))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！LLM 已成功接入。")
    else:
        print("⚠️  部分测试失败，请检查配置和网络连接。")
    print("=" * 60)


if __name__ == "__main__":
    main()

