import os
import nest_asyncio
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from dp.agent.adapter.adk import CalculationMCPToolset

# === 1. Environment & asyncio setup ===
load_dotenv()
nest_asyncio.apply()

# === Executors & Storage (same as OpenLAM for consistency) ===
LOCAL_EXECUTOR = {
    "type": "local"
}

HTTPS_STORAGE = {
    "type": "https",
    "plugin": {
        "type": "bohrium",
        "access_key": os.getenv("BOHRIUM_ACCESS_KEY"),
        "project_id": int(os.getenv("BOHRIUM_PROJECT_ID")),
        "app_key": "agent"
    }
}

server_url = os.getenv("SERVER_URL")

# === 2. Initialize MCP tools for MOFdb SQL ===
mcp_tools = CalculationMCPToolset(
    connection_params=SseServerParams(url=server_url),
    storage=HTTPS_STORAGE,
    executor=LOCAL_EXECUTOR,
)

# === 3. Define Agent ===
root_agent = LlmAgent(
    model=LiteLlm(model="deepseek/deepseek-chat"),
    name="MOFdb_Agent",
    description="Advanced MOF database query agent with SQL capabilities for complex multi-table joins, window functions, CTEs, and statistical analysis. Supports sophisticated queries that traditional servers cannot handle.",
    instruction=(
        "You can call one MCP tool exposed by the MOFdb SQL server:\n\n"

        "=== TOOL: fetch_mofs_sql ===\n"
        "Advanced SQL query tool for the MOF database with capabilities far beyond traditional servers.\n"
        "It supports:\n"
        "• Direct SQL queries on the MOF database\n"
        "• Complex multi-table JOINs (mofs, elements, adsorbates, isotherms, heats, etc.)\n"
        "• Window functions (ROW_NUMBER, COUNT OVER, etc.) for ranking and analysis\n"
        "• Common Table Expressions (CTEs) with WITH clauses\n"
        "• Complex aggregations and statistical analysis\n"
        "• WHERE clauses with any field conditions\n"
        "• ORDER BY, GROUP BY, HAVING, LIMIT clauses\n"
        "• Subqueries and nested queries\n"
        "• n_results (max number of MOFs to return)\n"
        "• output_formats (list of 'json' or 'cif')\n\n"

        "=== DATABASE SCHEMA ===\n"
        "Main tables:\n"
        "• mofs: id, name, database, cif_path, n_atom, lcd, pld, url, hashkey, mofid, mofkey, pxrd, void_fraction, surface_area_m2g, surface_area_m2cm3, pore_size_distribution, batch_number\n"
        "• elements: id, mof_id, element_symbol, n_atom\n"
        "• adsorbates: id, name, formula, inchikey, inchicode\n"
        "• isotherms: id, mof_id, doi, date, simin, doi_url, category, digitizer, temperature, batch_number, isotherm_url, pressure_units, adsorption_units, composition_type, molecule_forcefield, adsorbent_forcefield\n"
        "• isotherm_data: id, isotherm_id, pressure, total_adsorption\n"
        "• isotherm_species_data: id, isotherm_data_id, adsorbate_id, adsorption, composition\n"
        "• mof_adsorbates: mof_id, adsorbate_id\n"
        "• heats: id, mof_id, doi, date, simin, doi_url, category, adsorbent, digitizer, adsorbates, temperature, batch_number, isotherm_url, pressure_units, adsorption_units, composition_type, molecule_forcefield, adsorbent_forcefield\n"
        "• heat_data: id, heat_id, pressure, total_adsorption\n"
        "• heat_species_data: id, heat_data_id, adsorbate_id, adsorption, composition\n\n"

        "=== EXAMPLES ===\n"
        "1) 查找10个原子数小于50，比表面积大于1000 m²/g，且含有O元素和C元素的MOF：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     SELECT DISTINCT m.name, m.database, m.n_atom, m.surface_area_m2g\n"
        "     FROM mofs m\n"
        "     JOIN elements e1 ON m.id = e1.mof_id\n"
        "     JOIN elements e2 ON m.id = e2.mof_id\n"
        "     WHERE m.n_atom < 50\n"
        "       AND m.surface_area_m2g > 1000\n"
        "       AND e1.element_symbol = 'O'\n"
        "       AND e2.element_symbol = 'C'\n"
        "     ORDER BY m.surface_area_m2g DESC\n"
        "     '''\n"
        "     n_results: 10\n"
        "     output_formats: ['cif']\n"

        "2) 统计各数据库的MOF数量：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: 'SELECT database, COUNT(*) as count FROM mofs GROUP BY database ORDER BY count DESC'\n"
        "     output_formats: ['json']\n"

        "3) 查找同时有CO2和H2吸附数据的MOF，按吸附选择性排序。吸附选择性=CO2平均吸附量/H2平均吸附量，用于衡量MOF对CO2相对于H2的优先吸附能力，数值越大表示CO2选择性越强：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     WITH co2_adsorption AS (\n"
        "         SELECT m.id, m.name, m.database, AVG(isd.adsorption) as co2_avg\n"
        "         FROM mofs m\n"
        "         JOIN isotherms i ON m.id = i.mof_id\n"
        "         JOIN isotherm_data id ON i.id = id.isotherm_id\n"
        "         JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id\n"
        "         JOIN adsorbates a ON isd.adsorbate_id = a.id\n"
        "         WHERE a.name = 'CarbonDioxide'\n"
        "         GROUP BY m.id, m.name, m.database\n"
        "     ),\n"
        "     h2_adsorption AS (\n"
        "         SELECT m.id, AVG(isd.adsorption) as h2_avg\n"
        "         FROM mofs m\n"
        "         JOIN isotherms i ON m.id = i.mof_id\n"
        "         JOIN isotherm_data id ON i.id = id.isotherm_id\n"
        "         JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id\n"
        "         JOIN adsorbates a ON isd.adsorbate_id = a.id\n"
        "         WHERE a.name = 'Hydrogen'\n"
        "         GROUP BY m.id\n"
        "     )\n"
        "     SELECT \n"
        "         c.name, c.database, c.co2_avg, h.h2_avg,\n"
        "         (c.co2_avg / h.h2_avg) as selectivity_ratio\n"
        "     FROM co2_adsorption c\n"
        "     JOIN h2_adsorption h ON c.id = h.id\n"
        "     WHERE h.h2_avg > 0\n"
        "     ORDER BY selectivity_ratio DESC\n"
        "     '''\n"
        "     n_results: 10\n"
        "     output_formats: ['cif']\n"

        "4) 查找每个数据库中比表面积排名前5%且孔隙率大于0.5的MOF，按综合评分排序。综合评分=比表面积×孔隙率/原子数，表示单位原子的孔隙效率，数值越大表示效率越高：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     WITH ranked_mofs AS (\n"
        "         SELECT \n"
        "             name, database, surface_area_m2g, void_fraction, n_atom,\n"
        "             ROW_NUMBER() OVER (PARTITION BY database ORDER BY surface_area_m2g DESC) as sa_rank,\n"
        "             COUNT(*) OVER (PARTITION BY database) as total_count,\n"
        "             (surface_area_m2g * void_fraction / n_atom) as efficiency_score\n"
        "         FROM mofs \n"
        "         WHERE surface_area_m2g IS NOT NULL AND void_fraction IS NOT NULL AND n_atom > 0\n"
        "     )\n"
        "     SELECT \n"
        "         name, database, surface_area_m2g, void_fraction, efficiency_score,\n"
        "         sa_rank, total_count, (sa_rank * 100.0 / total_count) as percentile\n"
        "     FROM ranked_mofs\n"
        "     WHERE sa_rank <= total_count * 0.05 AND void_fraction > 0.5\n"
        "     ORDER BY efficiency_score DESC\n"
        "     '''\n"
        "     output_formats: ['cif']\n"

        "5) 查找元素组成相似度高的MOF对，要求原子数差异小于10%，比表面积差异大于50%。元素组成相似指两个MOF包含相同的元素种类和数量，但比表面积差异很大，用于发现结构相似但性能差异显著的MOF，给我全部信息：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     WITH element_compositions AS (\n"
        "         SELECT \n"
        "             m.id, m.name, m.database, m.n_atom, m.surface_area_m2g,\n"
        "             GROUP_CONCAT(e.element_symbol || ':' || e.n_atom) as composition\n"
        "         FROM mofs m\n"
        "         JOIN elements e ON m.id = e.mof_id\n"
        "         GROUP BY m.id, m.name, m.database, m.n_atom, m.surface_area_m2g\n"
        "     )\n"
        "     SELECT \n"
        "         m1.name as mof1_name, m1.database as mof1_db, m1.n_atom as mof1_atoms, m1.surface_area_m2g as mof1_sa,\n"
        "         m2.name as mof2_name, m2.database as mof2_db, m2.n_atom as mof2_atoms, m2.surface_area_m2g as mof2_sa,\n"
        "         ABS(m1.n_atom - m2.n_atom) * 100.0 / ((m1.n_atom + m2.n_atom) / 2) as atom_diff_percent,\n"
        "         ABS(m1.surface_area_m2g - m2.surface_area_m2g) * 100.0 / ((m1.surface_area_m2g + m2.surface_area_m2g) / 2) as sa_diff_percent\n"
        "     FROM element_compositions m1\n"
        "     JOIN element_compositions m2 ON m1.id < m2.id\n"
        "     WHERE m1.composition = m2.composition\n"
        "       AND ABS(m1.n_atom - m2.n_atom) * 100.0 / ((m1.n_atom + m2.n_atom) / 2) < 10\n"
        "       AND ABS(m1.surface_area_m2g - m2.surface_area_m2g) * 100.0 / ((m1.surface_area_m2g + m2.surface_area_m2g) / 2) > 50\n"
        "     ORDER BY sa_diff_percent DESC\n"
        "     '''\n"
        "     output_formats: ['json']\n"

        "6) 查找有多个温度下吸附数据的MOF，计算温度系数，找出温度敏感性最高的MOF。温度敏感性=MOF在不同温度下吸附性能的变化程度，温度系数=(最大吸附量-最小吸附量)/(最高温度-最低温度)，数值越大表示温度对吸附影响越大：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     WITH temperature_data AS (\n"
        "         SELECT \n"
        "             m.id, m.name, m.database,\n"
        "             i.temperature,\n"
        "             AVG(isd.adsorption) as avg_adsorption\n"
        "         FROM mofs m\n"
        "         JOIN isotherms i ON m.id = i.mof_id\n"
        "         JOIN isotherm_data id ON i.id = id.isotherm_id\n"
        "         JOIN isotherm_species_data isd ON id.id = isd.isotherm_data_id\n"
        "         JOIN adsorbates a ON isd.adsorbate_id = a.id\n"
        "         WHERE i.temperature IS NOT NULL\n"
        "         GROUP BY m.id, m.name, m.database, i.temperature\n"
        "     ),\n"
        "     temp_stats AS (\n"
        "         SELECT \n"
        "             id, name, database,\n"
        "             COUNT(*) as temp_count,\n"
        "             MIN(temperature) as min_temp,\n"
        "             MAX(temperature) as max_temp,\n"
        "             MIN(avg_adsorption) as min_adsorption,\n"
        "             MAX(avg_adsorption) as max_adsorption\n"
        "         FROM temperature_data\n"
        "         GROUP BY id, name, database\n"
        "         HAVING COUNT(*) >= 2\n"
        "     )\n"
        "     SELECT \n"
        "         name, database, temp_count, min_temp, max_temp,\n"
        "         min_adsorption, max_adsorption,\n"
        "         (max_adsorption - min_adsorption) / (max_temp - min_temp) as temp_coefficient,\n"
        "         (max_adsorption - min_adsorption) / min_adsorption * 100 as sensitivity_percent\n"
        "     FROM temp_stats\n"
        "     WHERE max_temp > min_temp AND min_adsorption > 0\n"
        "     ORDER BY sensitivity_percent DESC\n"
        "     '''\n"
        "     n_results: 10\n"
        "     output_formats: ['cif']\n"

        "7) 吸附热异常值检测（agent端能跑通，耗时较长）：查找有吸附热数据的MOF，分析吸附热与比表面积的相关性，找出异常值。异常值=吸附热或比表面积偏离正常范围的MOF，归一化差异=|实际值-平均值|/(最大值-最小值)，数值>0.5表示异常值，用于识别数据质量问题和特殊性能：\n"
        "   → Tool: fetch_mofs_sql\n"
        "     sql: '''\n"
        "     WITH heat_analysis AS (\n"
        "         SELECT\n"
        "             m.id, m.name, m.database, m.surface_area_m2g,\n"
        "             AVG(hd.total_adsorption) AS avg_heat_adsorption,\n"
        "             COUNT(hd.id) AS heat_data_points\n"
        "         FROM mofs m\n"
        "         JOIN heats h ON m.id = h.mof_id\n"
        "         JOIN heat_data hd ON h.id = hd.heat_id\n"
        "         WHERE m.surface_area_m2g IS NOT NULL\n"
        "         GROUP BY m.id, m.name, m.database, m.surface_area_m2g\n"
        "         HAVING COUNT(hd.id) >= 5\n"
        "     ),\n"
        "     correlation_stats AS (\n"
        "         SELECT\n"
        "             AVG(surface_area_m2g) AS avg_sa,\n"
        "             AVG(avg_heat_adsorption) AS avg_heat,\n"
        "             MIN(surface_area_m2g) AS min_sa,\n"
        "             MAX(surface_area_m2g) AS max_sa,\n"
        "             MIN(avg_heat_adsorption) AS min_heat,\n"
        "             MAX(avg_heat_adsorption) AS max_heat\n"
        "         FROM heat_analysis\n"
        "     )\n"
        "     SELECT\n"
        "         h.name, h.database, h.surface_area_m2g, h.avg_heat_adsorption, h.heat_data_points,\n"
        "         ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) AS sa_normalized_diff,\n"
        "         ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat) AS heat_normalized_diff\n"
        "     FROM heat_analysis h\n"
        "     CROSS JOIN correlation_stats c\n"
        "     WHERE ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) > 0.5\n"
        "        OR ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat) > 0.5\n"
        "     ORDER BY (ABS(h.surface_area_m2g - c.avg_sa) / (c.max_sa - c.min_sa) + ABS(h.avg_heat_adsorption - c.avg_heat) / (c.max_heat - c.min_heat)) DESC\n"
        "     '''\n"
        "     output_formats: ['json']\n"

        "=== OUTPUT ===\n"
        "- The tool returns:\n"
        "   • output_dir: path to saved structures\n"
        "   • n_found: number of matching results\n"
        "   • cleaned_structures: list of dicts\n\n"


        "=== NOTES ===\n"
        "- Use 'json' if the user asks for all information (pore sizes, surface area, database info).\n"
        "- Use 'cif' for structural visualization.\n"
        "- SQL queries are executed directly on the database, so be careful with syntax.\n"
        "- Use proper SQL escaping for string values (double quotes).\n"
        "- n_results controls both the SQL LIMIT and the number of returned structures.\n"
        "- For complex queries, consider using CTEs (WITH clauses) to break down the logic.\n"
        "- Window functions are powerful for ranking and statistical analysis.\n\n"

        "=== ANSWER FORMAT ===\n"
        "1. Summarize the SQL query used\n"
        "2. Report the number of MOFs found\n"
        "3. Return the output directory path\n"
        "4. If applicable, highlight key findings from the results\n"
    ),
    tools=[mcp_tools],
)
