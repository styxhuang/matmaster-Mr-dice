from pymatgen.core import Composition

formula = "TiO2"
hill_formula = Composition(formula).hill_formula.replace(' ', '')
print(hill_formula)  # ➜ O2Ti


