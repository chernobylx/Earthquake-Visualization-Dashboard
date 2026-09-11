"""The pixi tasks must run the notebook against this checkout, not against git.

apps/marimo_app.py carries PEP 723 metadata that installs earthquake-dashboard
from git so molab -- which mirrors the single .py file and nothing around it --
can resolve the package. `marimo run` honours that metadata by re-executing
itself under `uv run --isolated`, so the task silently serves whatever *main*
holds and never imports src/. A fix sitting in the working tree then appears not
to work: #43 removed the map brush from the heatmap's filters, Dash picked the
change up through its editable install and marimo did not, and the map brush
went on blanking the heatmap locally. --no-sandbox keeps local runs on the
editable install while leaving the metadata intact for molab.
"""
import tomllib
from pathlib import Path

PIXI = Path(__file__).resolve().parent.parent / 'pixi.toml'


def marimo_tasks() -> dict[str, str]:
    tasks = tomllib.loads(PIXI.read_text())['feature']['alt']['tasks']
    return {name: cmd for name, cmd in tasks.items()
            if isinstance(cmd, str) and cmd.startswith('marimo ')}


def test_marimo_tasks_exist():
    assert marimo_tasks(), 'no marimo tasks found in pixi.toml [feature.alt.tasks]'


def test_marimo_tasks_do_not_resolve_the_package_from_git():
    for name, cmd in marimo_tasks().items():
        assert '--no-sandbox' in cmd, (
            f"pixi task '{name}' runs '{cmd}'. Without --no-sandbox, marimo "
            'rebuilds the environment from the PEP 723 block and imports '
            'earthquake-dashboard from git, so changes in src/ are not tested.'
        )


def test_notebook_still_declares_the_git_source_for_molab():
    """--no-sandbox must not be "fixed" by deleting the metadata molab needs."""
    script = (PIXI.parent / 'apps' / 'marimo_app.py').read_text()
    assert 'tool.uv.sources' in script and 'git = ' in script
