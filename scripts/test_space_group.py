from pprint import pprint

from crystaldb.matching.space_group import compare_space_groups


rruff_sg = "P2_1/n"
cod_sg = "P 1 21/n 1"

result = compare_space_groups(
    rruff_sg,
    cod_sg,
)

pprint(result)