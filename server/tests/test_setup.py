import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch


PROJECT = Path(__file__).resolve().parents[2]
CHECK_RUNTIME = runpy.run_path(str(PROJECT / "scripts/check-runtime.py"))["check_runtime"]
RUNTIME_MODULES = ("fastapi", "uvicorn", "fitz", "pandas", "openpyxl", "httpx", "multipart", "jobspy")

# These stand-ins model the installer's external tools without downloading or
# installing packages. The real shell scripts still perform orchestration.
FAKE_TOOL = r'''
import json
import os
import shutil
import sys
from pathlib import Path

root = Path(os.environ["FAKE_ROOT"])
args = sys.argv[1:]
tool = Path(sys.argv[0]).name
with (root / "commands.jsonl").open("a") as output:
    output.write(json.dumps({"tool": tool, "args": args,
                             "python_install_dir": os.environ.get("UV_PYTHON_INSTALL_DIR")}) + "\n")

def create_runtime(directory, version="3.12", ready=False):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bin").mkdir(exist_ok=True)
    shutil.copyfile(os.environ["FAKE_TOOL_SOURCE"], directory / "bin/python")
    (directory / "bin/python").chmod(0o755)
    (directory / "state.json").write_text(json.dumps({"version": version, "ready": ready}))

if tool == "uv":
    if args[:2] == ["python", "find"]:
        sys.exit(int(os.environ.get("FAKE_PYTHON_MISSING", "0")))
    if args[:2] == ["python", "install"]:
        sys.exit(0)
    if args[0] == "venv":
        create_runtime(root / args[-1])
    elif args[:2] == ["pip", "install"]:
        state_file = root / ".venv/state.json"
        state = json.loads(state_file.read_text())
        state["ready"] = True
        state_file.write_text(json.dumps(state))
elif tool in ("python", "python3"):
    if args[:2] == ["-m", "venv"]:
        create_runtime(Path(args[2]))
    elif args[:3] == ["-m", "pip", "install"]:
        destination = Path(sys.argv[0]).parent / "uv"
        shutil.copyfile(os.environ["FAKE_TOOL_SOURCE"], destination)
        destination.chmod(0o755)
    else:
        state = json.loads((Path(sys.argv[0]).parent.parent / "state.json").read_text())
        if args[0] == "-c":
            sys.exit(0 if state["version"] == "3.12" else 1)
        if args[0] == "scripts/check-runtime.py":
            sys.exit(0 if state["version"] == "3.12" and state["ready"] else 1)
elif tool == "npm":
    if args[0] == "ci":
        (root / "node_modules").mkdir(exist_ok=True)
    elif args[:2] == ["run", "build"]:
        (root / "dist").mkdir(exist_ok=True)
        (root / "dist/index.html").write_text("Built frontend")
'''


class RuntimeReadinessTests(unittest.TestCase):
    def test_wrong_python_is_rejected_before_loading_dependencies(self):
        with patch.object(sys, "version_info", (3, 14, 0)), patch("importlib.import_module") as load:
            with self.assertRaisesRegex(RuntimeError, "Python 3.12"):
                CHECK_RUNTIME()
            load.assert_not_called()

    def test_incomplete_install_is_rejected(self):
        def load(module):
            if module == "pandas":
                raise ModuleNotFoundError("pandas")

        with patch.object(sys, "version_info", (3, 12, 0)), patch("importlib.import_module", side_effect=load):
            with self.assertRaisesRegex(ImportError, "pandas"):
                CHECK_RUNTIME()

    def test_complete_runtime_loads_every_required_component(self):
        with patch.object(sys, "version_info", (3, 12, 0)), patch("importlib.import_module") as load:
            CHECK_RUNTIME()
            self.assertEqual(load.call_args_list, [call(module) for module in RUNTIME_MODULES])


class SetupScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="tcc-setup-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "scripts").mkdir()
        for name in ("setup.sh", "start.sh", "check-runtime.py"):
            shutil.copyfile(PROJECT / "scripts" / name, self.root / "scripts" / name)
        self.bin = self.root / "fake-bin"
        self.bin.mkdir()
        self.source = self.root / "fake-tool.py"
        self.source.write_text(f"#!{sys.executable}\n" + FAKE_TOOL)
        self.source.chmod(0o755)
        for command in ("uv", "python3", "npm"):
            shutil.copyfile(self.source, self.bin / command)
            (self.bin / command).chmod(0o755)
        # A closed PATH ensures the no-uv case cannot find the host's uv.
        for command in ("bash", "dirname", "mkdir", "mv", "date", "find"):
            (self.bin / command).symlink_to(shutil.which(command))
        self.environment = {
            "PATH": str(self.bin),
            "FAKE_ROOT": str(self.root),
            "FAKE_TOOL_SOURCE": str(self.source),
        }

    def run_script(self, name):
        result = subprocess.run(
            [str(self.bin / "bash"), str(self.root / "scripts" / name)],
            cwd=self.root, env=self.environment, text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return [json.loads(line) for line in (self.root / "commands.jsonl").read_text().splitlines()]

    def create_runtime(self, version="3.12", ready=True):
        directory = self.root / ".venv"
        (directory / "bin").mkdir(parents=True)
        shutil.copyfile(self.source, directory / "bin/python")
        (directory / "bin/python").chmod(0o755)
        (directory / "state.json").write_text(json.dumps({"version": version, "ready": ready}))

    def test_setup_selects_python_312_and_requires_binary_data_packages(self):
        self.environment["FAKE_PYTHON_MISSING"] = "1"
        commands = self.run_script("setup.sh")
        uv = [item for item in commands if item["tool"] == "uv"]
        self.assertTrue(any(item["args"][:2] == ["python", "install"] and item["args"][-1] == "3.12" for item in uv))
        creation = next(item["args"] for item in uv if item["args"][0] == "venv")
        self.assertEqual(creation[creation.index("--python") + 1], "3.12")
        install = next(item["args"] for item in uv if item["args"][:2] == ["pip", "install"])
        self.assertEqual(install[install.index("--only-binary") + 1], "pandas,numpy")
        self.assertEqual(install[install.index("--python") + 1], ".venv/bin/python")
        self.assertTrue(all(item["python_install_dir"] == str(self.root / ".cache/python") for item in uv))
        self.assertTrue((self.root / "dist/index.html").is_file())

    def test_wrong_interpreter_is_preserved_before_replacement(self):
        self.create_runtime(version="3.14")
        (self.root / ".venv/user-file").write_text("preserve this")
        self.run_script("setup.sh")
        backups = list((self.root / ".cache/venv-backups").glob("venv-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "user-file").read_text(), "preserve this")
        self.assertEqual(json.loads((self.root / ".venv/state.json").read_text())["version"], "3.12")

    def test_start_repairs_interrupted_install_despite_existing_node_modules(self):
        self.create_runtime(ready=False)
        (self.root / "node_modules").mkdir()
        commands = self.run_script("start.sh")
        self.assertTrue(any(item["tool"] == "uv" and item["args"][:2] == ["pip", "install"] for item in commands))
        self.assertEqual(commands[-1]["args"][:3], ["-m", "uvicorn", "server.app:app"])
        self.assertTrue(json.loads((self.root / ".venv/state.json").read_text())["ready"])

    def test_missing_uv_bootstraps_in_an_isolated_local_environment(self):
        (self.bin / "uv").unlink()
        commands = self.run_script("setup.sh")
        bootstrap = self.root / ".cache/uv-bootstrap"
        creation = next(item for item in commands if item["tool"] == "python3")
        self.assertEqual(creation["args"], ["-m", "venv", str(bootstrap)])
        pip = next(item for item in commands if item["args"][:3] == ["-m", "pip", "install"])
        self.assertEqual(pip["tool"], "python")
        self.assertIn("--only-binary=:all:", pip["args"])
        self.assertTrue((bootstrap / "bin/uv").is_file())
        self.assertTrue((self.root / "dist/index.html").is_file())

    def test_complete_start_reuses_existing_dependencies_and_build(self):
        self.create_runtime()
        for directory in ("node_modules", "src", "public", "dist"):
            (self.root / directory).mkdir()
        for name in ("index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json"):
            (self.root / name).write_text("fixture")
        built = self.root / "dist/index.html"
        built.write_text("already built")
        fresh = max(path.stat().st_mtime for path in self.root.iterdir()) + 10
        os.utime(built, (fresh, fresh))
        commands = self.run_script("start.sh")
        self.assertFalse(any(item["tool"] in ("uv", "npm") for item in commands))
        self.assertEqual(commands[-1]["args"][:3], ["-m", "uvicorn", "server.app:app"])
