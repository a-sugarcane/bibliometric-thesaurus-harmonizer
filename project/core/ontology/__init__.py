"""MeSH Ontology compilation and fast offline inverted index lookup."""

from core.ontology.mesh_compiler import MeSHCompiler
from core.ontology.mesh_lookup import MeSHLookup, MeSHMatchResult

__all__ = ["MeSHCompiler", "MeSHLookup", "MeSHMatchResult"]
