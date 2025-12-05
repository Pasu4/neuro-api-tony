#!/bin/bash

set -ex -o pipefail

# Log some general info about the environment
echo "::group::Environment"
uname -a
env | sort
PROJECT='neuro_api_tony'
echo "::endgroup::"


################################################################
# We have a Python environment!
################################################################

echo "::group::Versions"
python -c "import sys, struct; print('python:', sys.version); print('version_info:', sys.version_info); print('bits:', struct.calcsize('P') * 8)"
echo "::endgroup::"

echo "::group::Install dependencies"
python -m pip install -U pip tomli
python -m pip --version
UV_VERSION=$(python -c 'import tomli; from pathlib import Path; print({p["name"]:p for p in tomli.loads(Path("uv.lock").read_text())["package"]}["uv"]["version"])')
WXPYTHON_VERSION=$(python -c 'import tomli; from pathlib import Path; print({p["name"]:p for p in tomli.loads(Path("uv.lock").read_text())["package"]}["wxpython"]["version"])')
python -m pip install uv=="$UV_VERSION"
python -m uv --version

UV_VENV_SEED="pip"
python -m uv venv --seed --allow-existing

# Determine the platform and activate the virtual environment accordingly
case "$OSTYPE" in
  linux-gnu*|linux-musl*|darwin*)
    source .venv/bin/activate
    ;;
  cygwin*|msys*)
    source .venv/Scripts/activate
    ;;
  *)
    echo "::error:: Unknown OS. Please add an activation method for '$OSTYPE'."
    exit 1
    ;;
esac

# Install uv in virtual environment
python -m pip install uv=="$UV_VERSION"

# Check if running on Linux and install wxPython from binaries
if [[ "${RUNNER_OS:-}" == "Linux" ]]; then
    echo "::group::Installing dependencies for Linux"
    sudo apt-get update -q
    sudo apt-get install -y -q python3-dev libgtk-3-dev libnotify-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libwebkit2gtk-4.1-dev libsdl2-2.0-0
    # Get the Ubuntu version
    UBUNTU_VERSION=$(lsb_release -rs)
    PYTHON_VERSION=$(python -c 'import sys; print("".join(map(str, sys.version_info[:2])))')
    if [[ "$PYTHON_VERSION" == "310" ]]; then
        # Can't install for wxpython 4.2.4 on python 3.10 because of see below, revert to wxpython 4.2.3
        WXPYTHON_VERSION="4.2.3"
    else
        uv pip install tomli tomli_w
        # For some reason wxpython 4.2.4 wheels need mark as requires >=3.11 to get uv to work properly?
        python -c 'import tomli, tomli_w; from pathlib import Path; path=Path("pyproject.toml"); file=tomli.loads(path.read_text()); file["project"]["requires-python"]=">=3.11"; path.write_text(tomli_w.dumps(file))'
    fi
    # Install wxPython from binaries
    WX_WHEEL_URL="https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-${UBUNTU_VERSION}/wxpython-${WXPYTHON_VERSION}-cp${PYTHON_VERSION}-cp${PYTHON_VERSION}-linux_x86_64.whl"
    if [[ "$PYTHON_VERSION" == "310" ]]; then
        uv pip install "wxPython @ ${WX_WHEEL_URL}"
    else
        uv add "wxPython @ ${WX_WHEEL_URL}"
    fi
    # Make sure installation was successful
    WX_RUN_VERSION=$(python -c "import wx; print(wx.__version__)")
    if [[ "${WX_RUN_VERSION}" != "${WXPYTHON_VERSION}" ]]; then
        echo "::error:: wxPython linux installation failed, version does not match expected."
        exit 1
    fi
    if [[ "$PYTHON_VERSION" == "310" ]]; then
        # See above
        uv add "wxPython~=$WXPYTHON_VERSION"
    fi
    echo "::endgroup::"
fi

if [ "$CHECK_FORMATTING" = "1" ]; then
    uv sync --extra tests --extra tools
    echo "::endgroup::"
    # Restore files to original state on Linux
    if [[ "${RUNNER_OS:-}" == "Linux" ]]; then
        git restore pyproject.toml uv.lock
    fi
    source check.sh
else
    # Actual tests
    # expands to 0 != 1 if NO_TEST_REQUIREMENTS is not set, if set the `-0` has no effect
    # https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_06_02
    if [ "${NO_TEST_REQUIREMENTS-0}" == 1 ]; then
        uv sync --extra tests
    else
        uv sync --extra tests --extra tools
    fi

    echo "::endgroup::"

    echo "::group::Setup for tests"

    # We run the tests from inside an empty directory, to make sure Python
    # doesn't pick up any .py files from our working dir. Might have been
    # pre-created by some of the code above.
    mkdir empty || true
    cd empty

    INSTALLDIR=$(python -c "import os, $PROJECT; print(os.path.dirname($PROJECT.__file__))")
    cp ../pyproject.toml "$INSTALLDIR"

    echo "::endgroup::"
    echo "::group:: Run Tests"
    if coverage run --rcfile=../pyproject.toml -m pytest -ra --junitxml=../test-results.xml ../tests --verbose --durations=10; then
        PASSED=true
    else
        PASSED=false
    fi
    PREV_DIR="$PWD"
    cd "$INSTALLDIR"
    rm pyproject.toml
    cd "$PREV_DIR"
    echo "::endgroup::"
    echo "::group::Coverage"

    coverage combine --rcfile ../pyproject.toml
    coverage report -m --rcfile ../pyproject.toml
    coverage xml --rcfile ../pyproject.toml

    echo "::endgroup::"
    $PASSED
fi
