"""Configuration-file adapters.

Isolates the "I read a YAML config file and expose it as a port" work
from every other adapter category. Governed by the
``config-adapter-is-self-contained`` import-linter contract.
"""

from __future__ import annotations

from vidscope.adapters.config.yaml_taxonomy import YamlTaxonomy
from vidscope.adapters.config.yaml_vocabulary import YamlVocabularySource

__all__ = ["YamlTaxonomy", "YamlVocabularySource"]
