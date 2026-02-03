from optimade.client import OptimadeClient
from optimade.adapters.structures import Structure
import jmespath


# Step 1: Create client and fetch structures
client = OptimadeClient(include_providers={"mp"}, max_results_per_provider=2

)
results = client.get(filter='elements HAS ALL "Si", "O", "Al"')

structure_data1 = jmespath.search("structures.*.*.data", results)[0][0][0]
structure_data2 = jmespath.search("structures.*.*.data", results)[0][0][1]


cif1 = Structure(structure_data1).convert('cif')
cif2 = Structure(structure_data2).convert('cif')

print(cif1)
print(cif2)