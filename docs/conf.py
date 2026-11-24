# Configuration file for the Sphinx documentation builder.
#
# Most settings come from sphinx-astropy (numpydoc, automodapi, intersphinx, the pydata
# theme); MyST lets the pages be written in Markdown.

from sphinx_astropy.conf.v2 import *  # noqa: F403

from multi_eyes import __version__

project = "multi_eyes"
author = "Matteo Bachetti"
copyright = "2026, Matteo Bachetti"
release = __version__
version = __version__.split("+")[0]

extensions += ["myst_parser"]  # noqa: F405
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
myst_heading_anchors = 3
# towncrier snippets are folded into CHANGES.rst; they are not pages.
exclude_patterns += ["changes", "_build"]  # noqa: F405

intersphinx_mapping.update(  # noqa: F405
    {"astroquery": ("https://astroquery.readthedocs.io/en/latest/", None)}
)

html_theme_options.update(  # noqa: F405
    {"github_url": "https://github.com/matteobachetti/multi_eyes"}
)
html_title = f"multi_eyes {version}"
