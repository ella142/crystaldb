from pprint import pprint

from crystaldb.cif_parser import parse_cif


path = r"D:\document\aiformaterials\crystaldb\data\raw\cod\9000253.cif"

structure = parse_cif(path)

pprint(structure)