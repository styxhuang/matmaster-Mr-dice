from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure
import jmespath
from pymatgen.core import Composition

def hill_formula_filter(formula: str) -> str:
    """
    Converts a chemical formula to Hill notation for OPTIMADE filtering.

    Parameters:
        formula (str): The chemical formula, e.g., "TiO2".

    Returns:
        str: A filter string for OPTIMADE using the Hill formula.
    """
    hill_formula = Composition(formula).hill_formula.replace(' ', '')
    return f'chemical_formula_reduced="{hill_formula}"'


# Step 1: Create client and fetch structures
client = OptimadeClient(
    include_providers={"mp"},
    max_results_per_provider=2,
)

# Step 2: Use the function to prepare the filter
formula = "ZrO"
filter_str = hill_formula_filter(formula)

# Step 3: Fetch results with that filter
results = client.get(filter=filter_str)
print(results)

# Step 4: Extract structures from results
structure_data_list = jmespath.search("structures.*.*.data", results)[0][0]
structure_data1 = structure_data_list[0]
structure_data2 = structure_data_list[1]

# Step 5: Convert to CIF format
cif1 = Structure(structure_data1).convert('cif')
cif2 = Structure(structure_data2).convert('cif')

print(cif1)
print(cif2)