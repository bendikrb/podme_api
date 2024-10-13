from importlib.metadata import Distribution
from pathlib import Path
import sys

import sphinx_book_theme

ROOT_DIR = Path(__file__).parents[2].absolute()

sys.path.insert(0, ROOT_DIR.as_posix())


dist = Distribution.from_name("podme_api")

project = dist.name
author = f"{dist.metadata.get("author")} <{dist.metadata.get("author_email")}>"
release = dist.version

html_theme = "sphinx_book_theme"
html_theme_path = [sphinx_book_theme.get_html_theme_path()]
html_theme_options = {
    "repository_url": "https://github.com/bendikrb/podme_api",
    "use_repository_button": True,
}

extensions = [
    "sphinx.ext.napoleon",
    "enum_tools.autoenum",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx.ext.autodoc.typehints",
    "sphinx_toolbox.more_autodoc.autotypeddict",
    "myst_parser",
]
templates_path = ["_templates"]
html_static_path = ["_static"]
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable", None),
    "yarl": ("https://yarl.aio-libs.org/en/stable", None),
}


autoclass_content = "class"
autodoc_typehints = "description"
autodoc_typehints_description_target = "all"
autodoc_member_order = "bysource"
autodoc_class_signature = "separated"
autodoc_typehints_format = "short"
# autodoc_preserve_defaults = True

autodoc_default_options = {
    "members": True,
    "inherited-members": "BaseDataClassORJSONMixin, DataClassORJSONMixin, StrEnum, IntEnum, str, Enum, dict, object",
    "exclude-members": "Config, from_dict, from_dict_json, from_json, to_dict, to_dict_json, to_dict_jsonb, to_jsonb, __init__, __new__",
    "undoc-members": True,
    "show-inheritance": True,
}

source_suffix = ".rst"
