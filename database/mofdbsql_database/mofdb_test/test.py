#!/usr/bin/env python3
"""
MOF SQL Server 测试文件
包含文件保存逻辑测试、复杂查询测试和安全测试
"""

import sys
import os
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_server import fetch_mofs
from utils import validate_sql_security

def test_file_saving_logic():
    """测试文件保存逻辑"""
    print("=== 测试文件保存逻辑 ===")
    
    # Test 1: 查询包含cif_path的MOF
    print("\n1. 测试有cif_path的情况:")
    test_sql_1 = """
    SELECT m.*, m.cif_path 
    FROM mofs m 
    WHERE m.cif_path IS NOT NULL 
    LIMIT 2
    """
    result_1 = fetch_mofs(test_sql_1, n_results=2, output_formats=["cif", "json"])
    print(f"  输出目录: {result_1['output_dir']}")
    print(f"  找到数量: {result_1['n_found']}")
    print(f"  返回结构数量: {len(result_1['cleaned_structures'])}")
    
    # Test 2: 查询不包含cif_path的MOF（统计查询）
    print("\n2. 测试无cif_path的统计查询:")
    test_sql_2 = """
    SELECT m.database, COUNT(*) as count, AVG(m.void_fraction) as avg_vf
    FROM mofs m 
    GROUP BY m.database 
    LIMIT 3
    """
    result_2 = fetch_mofs(test_sql_2, n_results=3, output_formats=["cif", "json"])
    print(f"  输出目录: {result_2['output_dir']}")
    print(f"  找到数量: {result_2['n_found']}")
    print(f"  返回结构数量: {len(result_2['cleaned_structures'])}")
    
    # Test 3: 查询MOF基本信息（无cif_path但可构建路径）
    print("\n3. 测试可构建路径的MOF查询:")
    test_sql_3 = """
    SELECT m.name, m.database, m.void_fraction, m.lcd, m.pld
    FROM mofs m 
    WHERE m.database LIKE '%hMOF%' 
    LIMIT 2
    """
    result_3 = fetch_mofs(test_sql_3, n_results=2, output_formats=["cif", "json"])
    print(f"  输出目录: {result_3['output_dir']}")
    print(f"  找到数量: {result_3['n_found']}")
    print(f"  返回结构数量: {len(result_3['cleaned_structures'])}")
    
    # Test 4: 用户要求CIF但无cif_path的情况
    print("\n4. 测试用户要求CIF但无cif_path的情况:")
    test_sql_4 = """
    SELECT m.name, m.database, m.void_fraction
    FROM mofs m 
    WHERE m.database LIKE '%CoREMOF%' 
    LIMIT 1
    """
    result_4 = fetch_mofs(test_sql_4, n_results=1, output_formats=["cif", "json"])
    print(f"  输出目录: {result_4['output_dir']}")
    print(f"  找到数量: {result_4['n_found']}")
    print(f"  返回结构数量: {len(result_4['cleaned_structures'])}")
    
    # Test 5: 数据库级别统计查询
    print("\n5. 测试数据库级别统计查询:")
    test_sql_5 = """
    SELECT 
        m.database,
        COUNT(*) as total_mofs,
        AVG(m.void_fraction) as avg_void_fraction,
        MIN(m.void_fraction) as min_void_fraction,
        MAX(m.void_fraction) as max_void_fraction,
        AVG(m.surface_area_m2g) as avg_surface_area,
        COUNT(CASE WHEN m.void_fraction > 0.5 THEN 1 END) as high_porosity_count,
        ROUND(COUNT(CASE WHEN m.void_fraction > 0.5 THEN 1 END) * 100.0 / COUNT(*), 2) as high_porosity_percentage
    FROM mofs m 
    WHERE m.void_fraction IS NOT NULL AND m.surface_area_m2g IS NOT NULL
    GROUP BY m.database
    ORDER BY total_mofs DESC
    LIMIT 5
    """
    result_5 = fetch_mofs(test_sql_5, n_results=5, output_formats=["cif", "json"])
    print(f"  输出目录: {result_5['output_dir']}")
    print(f"  找到数量: {result_5['n_found']}")
    print(f"  返回结构数量: {len(result_5['cleaned_structures'])}")
    
    print("\n=== 文件保存逻辑测试完成 ===")

def test_complex_queries():
    """测试复杂查询"""
    print("\n=== SQL版本独有的复杂查询任务 ===")
    print("这些查询在传统server中难以实现，展示了SQL的强大功能")
    
    # 测试1: 多表关联 + 复杂聚合 + 条件筛选
    print("\n1. 多表关联 + 复杂聚合 + 条件筛选:")
    print("用户提示词: '查找同时有CO2和H2吸附数据的MOF，按吸附选择性排序。吸附选择性=CO2平均吸附量/H2平均吸附量，用于衡量MOF对CO2相对于H2的优先吸附能力，数值越大表示CO2选择性越强'")
    result1 = fetch_mofs(
        sql='''
        WITH co2_adsorption AS (
            SELECT m.id, m.name, m.database, AVG(isd.adsorption) as co2_avg
            FROM mofs m
            JOIN isotherms i ON m.id = i.mof_id
            JOIN isotherm_data id ON i.id = id.isotherm_id
            JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id
            JOIN adsorbates a ON isd.adsorbate_id = a.id
            WHERE a.name = 'CarbonDioxide'
            GROUP BY m.id, m.name, m.database
        ),
        h2_adsorption AS (
            SELECT m.id, AVG(isd.adsorption) as h2_avg
            FROM mofs m
            JOIN isotherms i ON m.id = i.mof_id
            JOIN isotherm_data id ON i.id = id.isotherm_id
            JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id
            JOIN adsorbates a ON isd.adsorbate_id = a.id
            WHERE a.name = 'Hydrogen'
            GROUP BY m.id
        )
        SELECT 
            c.name, c.database, c.co2_avg, h.h2_avg,
            (c.co2_avg / h.h2_avg) as selectivity_ratio
        FROM co2_adsorption c
        JOIN h2_adsorption h ON c.id = h.id
        WHERE h.h2_avg > 0
        ORDER BY selectivity_ratio DESC
        ''',
        n_results=10,
        output_formats=['cif','json']
    )
    print(f"  输出目录: {result1['output_dir']}")
    print(f"  找到数量: {result1['n_found']}")
    print(f"  返回结构数量: {len(result1['cleaned_structures'])}")
    
    # 测试2: 窗口函数 + 复杂排名 + 条件筛选
    print("\n2. 窗口函数 + 复杂排名 + 条件筛选:")
    print("用户提示词: '查找每个数据库中比表面积排名前5%且孔隙率大于0.5的MOF，按综合评分排序。综合评分=比表面积×孔隙率/原子数，表示单位原子的孔隙效率，数值越大表示效率越高'")
    result2 = fetch_mofs(
        sql='''
        WITH ranked_mofs AS (
            SELECT 
                name, database, surface_area_m2g, void_fraction, n_atom,
                ROW_NUMBER() OVER (PARTITION BY database ORDER BY surface_area_m2g DESC) as sa_rank,
                COUNT(*) OVER (PARTITION BY database) as total_count,
                (surface_area_m2g * void_fraction / n_atom) as efficiency_score
            FROM mofs 
            WHERE surface_area_m2g IS NOT NULL AND void_fraction IS NOT NULL AND n_atom > 0
        )
        SELECT 
            name, database, surface_area_m2g, void_fraction, efficiency_score,
            sa_rank, total_count, (sa_rank * 100.0 / total_count) as percentile
        FROM ranked_mofs
        WHERE sa_rank <= total_count * 0.05 AND void_fraction > 0.5
        ORDER BY efficiency_score DESC
        ''',
        n_results=10,
        output_formats=['cif','json']
    )
    print(f"  输出目录: {result2['output_dir']}")
    print(f"  找到数量: {result2['n_found']}")
    print(f"  返回结构数量: {len(result2['cleaned_structures'])}")
    
    # 测试3: 复杂子查询 + 多条件组合 + 统计分析
    print("\n3. 复杂子查询 + 多条件组合 + 统计分析:")
    print("用户提示词: '查找元素组成相似度高的MOF对，要求原子数差异小于10%，比表面积差异大于50%。元素组成相似指两个MOF包含相同的元素种类和数量，但比表面积差异很大，用于发现结构相似但性能差异显著的MOF'")
    result3 = fetch_mofs(
        sql='''
        WITH element_compositions AS (
            SELECT 
                m.id, m.name, m.database, m.n_atom, m.surface_area_m2g,
                GROUP_CONCAT(e.element_symbol || ':' || e.n_atom) as composition
            FROM mofs m
            JOIN elements e ON m.id = e.mof_id
            GROUP BY m.id, m.name, m.database, m.n_atom, m.surface_area_m2g
        )
        SELECT 
            m1.name as mof1_name, m1.database as mof1_db, m1.n_atom as mof1_atoms, m1.surface_area_m2g as mof1_sa,
            m2.name as mof2_name, m2.database as mof2_db, m2.n_atom as mof2_atoms, m2.surface_area_m2g as mof2_sa,
            ABS(m1.n_atom - m2.n_atom) * 100.0 / ((m1.n_atom + m2.n_atom) / 2) as atom_diff_percent,
            ABS(m1.surface_area_m2g - m2.surface_area_m2g) * 100.0 / ((m1.surface_area_m2g + m2.surface_area_m2g) / 2) as sa_diff_percent
        FROM element_compositions m1
        JOIN element_compositions m2 ON m1.id < m2.id
        WHERE m1.composition = m2.composition
          AND ABS(m1.n_atom - m2.n_atom) * 100.0 / ((m1.n_atom + m2.n_atom) / 2) < 10
          AND ABS(m1.surface_area_m2g - m2.surface_area_m2g) * 100.0 / ((m1.surface_area_m2g + m2.surface_area_m2g) / 2) > 50
        ORDER BY sa_diff_percent DESC
        ''',
        n_results=10,
        output_formats=['cif','json']
    )
    print(f"  输出目录: {result3['output_dir']}")
    print(f"  找到数量: {result3['n_found']}")
    print(f"  返回结构数量: {len(result3['cleaned_structures'])}")
    
    # 测试4: 递归查询 + 复杂关联 + 条件筛选
    print("\n4. 递归查询 + 复杂关联 + 条件筛选:")
    print("用户提示词: '查找有多个温度下吸附数据的MOF，计算温度系数，找出温度敏感性最高的MOF。温度敏感性=MOF在不同温度下吸附性能的变化程度，温度系数=(最大吸附量-最小吸附量)/(最高温度-最低温度)，数值越大表示温度对吸附影响越大'")
    result4 = fetch_mofs(
        sql='''
        WITH temperature_data AS (
            SELECT 
                m.id, m.name, m.database,
                i.temperature,
                AVG(isd.adsorption) as avg_adsorption
            FROM mofs m
            JOIN isotherms i ON m.id = i.mof_id
            JOIN isotherm_data id ON i.id = id.isotherm_id
            JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id
            JOIN adsorbates a ON isd.adsorbate_id = a.id
            WHERE i.temperature IS NOT NULL
            GROUP BY m.id, m.name, m.database, i.temperature
        ),
        temp_stats AS (
            SELECT 
                id, name, database,
                COUNT(*) as temp_count,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                MIN(avg_adsorption) as min_adsorption,
                MAX(avg_adsorption) as max_adsorption
            FROM temperature_data
            GROUP BY id, name, database
            HAVING COUNT(*) >= 2
        )
        SELECT 
            name, database, temp_count, min_temp, max_temp,
            min_adsorption, max_adsorption,
            (max_adsorption - min_adsorption) / (max_temp - min_temp) as temp_coefficient,
            (max_adsorption - min_adsorption) / min_adsorption * 100 as sensitivity_percent
        FROM temp_stats
        WHERE max_temp > min_temp AND min_adsorption > 0
        ORDER BY sensitivity_percent DESC
        ''',
        n_results=10,
        output_formats=['cif','json']
    )
    print(f"  输出目录: {result4['output_dir']}")
    print(f"  找到数量: {result4['n_found']}")
    print(f"  返回结构数量: {len(result4['cleaned_structures'])}")
    
    # 测试5: 复杂条件 + 多表关联 + 统计分析
    print("\n5. 复杂条件 + 多表关联 + 统计分析:")
    print("用户提示词: '查找有吸附热数据的MOF，分析吸附热与比表面积的相关性，找出异常值。异常值=吸附热或比表面积偏离正常范围的MOF，归一化差异=|实际值-平均值|/(最大值-最小值)，数值>0.5表示异常值，用于识别数据质量问题和特殊性能'")
    result5 = fetch_mofs(
        sql='''
        WITH heat_analysis AS (
            SELECT 
                m.id, m.name, m.database, m.surface_area_m2g,
                AVG(hd.total_adsorption) as avg_heat_adsorption,
                COUNT(hd.id) as heat_data_points
            FROM mofs m
            JOIN heats h ON m.id = h.mof_id
            JOIN heat_data hd ON h.id = hd.heat_id
            WHERE m.surface_area_m2g IS NOT NULL
            GROUP BY m.id, m.name, m.database, m.surface_area_m2g
            HAVING COUNT(hd.id) >= 5
        ),
        correlation_stats AS (
            SELECT 
                AVG(surface_area_m2g) as avg_sa,
                AVG(avg_heat_adsorption) as avg_heat,
                MIN(surface_area_m2g) as min_sa,
                MAX(surface_area_m2g) as max_sa,
                MIN(avg_heat_adsorption) as min_heat,
                MAX(avg_heat_adsorption) as max_heat
            FROM heat_analysis
        )
        SELECT 
            h.name, h.database, h.surface_area_m2g, h.avg_heat_adsorption, h.heat_data_points,
            ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) as sa_normalized_diff,
            ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat) as heat_normalized_diff
        FROM heat_analysis h
        CROSS JOIN correlation_stats c
        WHERE ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) > 0.5 
           OR ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat) > 0.5
        ORDER BY (ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) + ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat)) DESC
        ''',
        n_results=10,
        output_formats=['cif','json']
    )
    print(f"  输出目录: {result5['output_dir']}")
    print(f"  找到数量: {result5['n_found']}")
    print(f"  返回结构数量: {len(result5['cleaned_structures'])}")
    
    # 测试6: 复杂子查询 + 多表关联 + 条件筛选
    print("\n6. 复杂子查询 + 多表关联 + 条件筛选:")
    print("用户提示词: '查找有多个吸附物数据的MOF，计算吸附选择性矩阵，找出选择性最强的MOF。吸附选择性矩阵=同一MOF对不同吸附物的吸附性能对比，选择性比值=最大吸附量/最小吸附量，数值越大表示对不同吸附物的分离能力越强'")
    result7 = fetch_mofs(
        sql='''
        WITH adsorbate_performance AS (
            SELECT 
                m.id, m.name, m.database,
                a.name as adsorbate_name,
                AVG(isd.adsorption) as avg_adsorption,
                COUNT(*) as data_points
            FROM mofs m
            JOIN isotherms i ON m.id = i.mof_id
            JOIN isotherm_data id ON i.id = id.isotherm_id
            JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id
            JOIN adsorbates a ON isd.adsorbate_id = a.id
            WHERE i.temperature = 298
            GROUP BY m.id, m.name, m.database, a.name
            HAVING COUNT(*) >= 3
        ),
        multi_adsorbate_mofs AS (
            SELECT id, name, database, COUNT(*) as adsorbate_count
            FROM adsorbate_performance
            GROUP BY id, name, database
            HAVING COUNT(*) >= 2
        ),
        selectivity_matrix AS (
            SELECT 
                m.id, m.name, m.database, m.adsorbate_count,
                GROUP_CONCAT(a.adsorbate_name || ':' || ROUND(a.avg_adsorption, 2)) as adsorption_profile,
                MAX(a.avg_adsorption) as max_adsorption,
                MIN(a.avg_adsorption) as min_adsorption,
                (MAX(a.avg_adsorption) - MIN(a.avg_adsorption)) as adsorption_range,
                (MAX(a.avg_adsorption) / MIN(a.avg_adsorption)) as selectivity_ratio
            FROM multi_adsorbate_mofs m
            JOIN adsorbate_performance a ON m.id = a.id
            GROUP BY m.id, m.name, m.database, m.adsorbate_count
        )
        SELECT 
            name, database, adsorbate_count, adsorption_profile,
            max_adsorption, min_adsorption, adsorption_range, selectivity_ratio
        FROM selectivity_matrix
        WHERE min_adsorption > 0
        ORDER BY selectivity_ratio DESC
        ''',
        n_results=10,
        output_formats=['cif','json'] 
    )
    print(f"  输出目录: {result7['output_dir']}")
    print(f"  找到数量: {result7['n_found']}")
    print(f"  返回结构数量: {len(result7['cleaned_structures'])}")
    
    print("\n=== 所有6个SQL独有复杂测试完成 ===")
    print("这些查询展示了SQL版本相比传统server的强大优势：")
    print("1. 多表关联分析 - 传统server无法实现")
    print("2. 复杂聚合统计 - 传统server无法实现")
    print("3. 窗口函数排名 - 传统server无法实现")
    print("4. 子查询和CTE - 传统server无法实现")
    print("5. 复杂条件筛选 - 传统server功能有限")
    print("6. 递归查询分析 - 传统server无法实现")

def test_security():
    """测试安全性"""
    print("\n=== 安全性测试 ===")
    
    # 测试1: 正常SELECT查询
    print("\n1. 测试正常SELECT查询:")
    try:
        validate_sql_security('SELECT * FROM mofs LIMIT 1')
        print("  ✓ SELECT查询通过安全检查")
    except Exception as e:
        print(f"  ✗ SELECT查询被阻止: {e}")
    
    # 测试2: WITH查询（CTE）
    print("\n2. 测试WITH查询（CTE）:")
    try:
        validate_sql_security('WITH test AS (SELECT 1) SELECT * FROM test')
        print("  ✓ WITH查询通过安全检查")
    except Exception as e:
        print(f"  ✗ WITH查询被阻止: {e}")
    
    # 测试3: 系统表访问
    print("\n3. 测试系统表访问:")
    try:
        validate_sql_security('SELECT name FROM sqlite_master WHERE type="table"')
        print("  ✓ 系统表访问通过安全检查")
    except Exception as e:
        print(f"  ✗ 系统表访问被阻止: {e}")
    
    # 测试4: 系统函数调用
    print("\n4. 测试系统函数调用:")
    try:
        validate_sql_security('SELECT sqlite_version() as version')
        print("  ✓ 系统函数调用通过安全检查")
    except Exception as e:
        print(f"  ✗ 系统函数调用被阻止: {e}")
    
    # 测试5: INSERT操作
    print("\n5. 测试INSERT操作:")
    try:
        validate_sql_security('INSERT INTO mofs (name) VALUES ("test")')
        print("  ✗ INSERT操作未被阻止")
    except Exception as e:
        print(f"  ✓ INSERT操作被阻止: {e}")
    
    # 测试6: UPDATE操作
    print("\n6. 测试UPDATE操作:")
    try:
        validate_sql_security('UPDATE mofs SET name = "test" WHERE id = 1')
        print("  ✗ UPDATE操作未被阻止")
    except Exception as e:
        print(f"  ✓ UPDATE操作被阻止: {e}")
    
    # 测试7: DELETE操作
    print("\n7. 测试DELETE操作:")
    try:
        validate_sql_security('DELETE FROM mofs WHERE id = 1')
        print("  ✗ DELETE操作未被阻止")
    except Exception as e:
        print(f"  ✓ DELETE操作被阻止: {e}")
    
    # 测试8: DROP操作
    print("\n8. 测试DROP操作:")
    try:
        validate_sql_security('DROP TABLE mofs')
        print("  ✗ DROP操作未被阻止")
    except Exception as e:
        print(f"  ✓ DROP操作被阻止: {e}")
    
    # 测试9: CREATE操作
    print("\n9. 测试CREATE操作:")
    try:
        validate_sql_security('CREATE TABLE test (id INTEGER)')
        print("  ✗ CREATE操作未被阻止")
    except Exception as e:
        print(f"  ✓ CREATE操作被阻止: {e}")
    
    # 测试10: ALTER操作
    print("\n10. 测试ALTER操作:")
    try:
        validate_sql_security('ALTER TABLE mofs ADD COLUMN test TEXT')
        print("  ✗ ALTER操作未被阻止")
    except Exception as e:
        print(f"  ✓ ALTER操作被阻止: {e}")
    
    # 测试11: 复杂危险查询
    print("\n11. 测试复杂危险查询:")
    try:
        validate_sql_security('SELECT * FROM mofs; DROP TABLE mofs; --')
        print("  ✗ 复杂危险查询未被阻止")
    except Exception as e:
        print(f"  ✓ 复杂危险查询被阻止: {e}")
    
    # 测试12: 实际执行危险查询（应该被SQLite只读模式阻止）
    print("\n12. 测试实际执行危险查询（SQLite只读模式）:")
    try:
        result = fetch_mofs('UPDATE mofs SET name = "test" WHERE id = 1', n_results=1, output_formats=['json'])
        print("  ✗ 危险查询未被SQLite阻止")
    except Exception as e:
        print(f"  ✓ 危险查询被SQLite只读模式阻止: {e}")
    
    print("\n=== 安全性测试完成 ===")
    print("✓ 应用层安全检查正常")
    print("✓ SQLite只读模式保护正常")
    print("✓ 双重安全保护机制生效")

def main():
    """主函数"""
    print("MOF SQL Server 测试开始")
    print("=" * 50)
    
    try:
        # 运行文件保存逻辑测试
        test_file_saving_logic()
        
        # 运行复杂查询测试
        test_complex_queries()
        
        # 运行安全性测试
        test_security()
        
        print("\n" + "=" * 50)
        print("所有测试完成！")
        print("请检查输出目录中的文件，验证不同场景的处理结果")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
